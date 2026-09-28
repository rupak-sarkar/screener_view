"""
Single-file proxy connecting Cline (VS Code) to Gemini Enterprise Backend.
Requires: pip install fastapi uvicorn google-auth
"""
import os
import re
import json
import codecs
import threading
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

# =============================================================================
# ENTERPRISE BACKEND CONFIGURATION
# =============================================================================

GE_PROJECT = os.environ.get("GE_PROJECT", "520175819682")
GE_LOCATION = os.environ.get("GE_LOCATION", "global")
GE_COLLECTION = os.environ.get("GE_COLLECTION", "default_collection")
GE_ENGINE = os.environ.get("GE_ENGINE", "gemini-prod-global_1775193874909")
GE_ASSISTANT = os.environ.get("GE_ASSISTANT", "default_assistant")
GE_AGENT_ID = os.environ.get("GE_AGENT_ID", "2256142418111018541")
GE_AGENT_VERSION = os.environ.get("GE_AGENT_VERSION", "deployed")
GE_TIME_ZONE = os.environ.get("GE_TIME_ZONE", "Asia/Calcutta")
GE_LANGUAGE_CODE = os.environ.get("GE_LANGUAGE_CODE", "en-US")

DISCOVERY_API_ROOT = "https://discoveryengine.googleapis.com"
CONTENT_API_ROOT = "https://content-discoveryengine.googleapis.com"
SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
CREDENTIAL_FILE = Path(os.environ.get("GE_CREDENTIAL_FILE", "service-account.json"))

HTTP_TIMEOUT_SECONDS = int(os.environ.get("GE_HTTP_TIMEOUT_SECONDS", "600"))
TOKEN_REFRESH_BUFFER_SECONDS = int(os.environ.get("GE_TOKEN_REFRESH_BUFFER_SECONDS", "300"))
STREAM_CHUNK_SIZE = 4096

# =============================================================================
# BACKEND CLASSES
# =============================================================================

class GeminiAgentError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code

class StreamingHttpResponse:
    def __init__(self, response: Any):
        self.response = response

    def iter_content(self, chunk_size: int = STREAM_CHUNK_SIZE) -> Iterator[str]:
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            while True:
                chunk = self.response.read(chunk_size)
                if not chunk:
                    tail = decoder.decode(b"", final=True)
                    if tail: yield tail
                    break
                text = decoder.decode(chunk)
                if text: yield text
        finally:
            self.response.close()

class GeminiEnterpriseBackend:
    def __init__(self) -> None:
        self.project, self.location = GE_PROJECT, GE_LOCATION
        self.collection, self.engine = GE_COLLECTION, GE_ENGINE
        self.assistant, self.agent_version = GE_ASSISTANT, GE_AGENT_VERSION
        self.time_zone, self.language_code = GE_TIME_ZONE, GE_LANGUAGE_CODE
        self.credential_file = CREDENTIAL_FILE
        self._credentials: Any = None
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._session: str | None = None
        self._lock = threading.RLock()

    def initialize(self) -> None:
        with self._lock:
            token = self._get_access_token()
            if not self._session:
                self._session = self._create_session(token)

    def chat(self, prompt: str, *, agent_id: str = GE_AGENT_ID) -> dict[str, Any]:
        with self._lock:
            token = self._get_access_token()
            if not self._session:
                self._session = self._create_session(token)
            session = self._session

        events = self._stream_assist(token, session, agent_id, prompt)
        answer_text = self._collect_answer_text(events)
        parsed_json = self._try_extract_json(answer_text)

        return {
            "success": True,
            "response": answer_text,
            "parsed_json": parsed_json,
        }

    def _resource_prefix(self) -> str:
        return f"projects/{self.project}/locations/{self.location}/collections/{self.collection}/engines/{self.engine}"

    def _get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        buffer = timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS)
        if self._token and self._token_expiry and now + buffer < self._token_expiry:
            return self._token

        if self._credentials is None:
            path = self.credential_file.resolve()
            if not path.is_file():
                path = Path.cwd() / self.credential_file
            self._credentials = service_account.Credentials.from_service_account_file(str(path), scopes=list(SCOPES))
        
        self._credentials.refresh(GoogleAuthRequest())
        self._token = self._credentials.token
        expiry = self._credentials.expiry
        self._token_expiry = expiry if expiry and expiry.tzinfo else (
            expiry.replace(tzinfo=timezone.utc) if expiry else now + timedelta(minutes=50)
        )
        return self._token

    def _post_json(self, url: str, token: str, payload: dict[str, Any], *, stream: bool = False) -> Any:
        req = Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        response = urlopen(req, timeout=HTTP_TIMEOUT_SECONDS)
        if stream: return StreamingHttpResponse(response)
        with response: return json.loads(response.read().decode("utf-8"))

    def _create_session(self, token: str) -> str:
        data = self._post_json(
            f"{DISCOVERY_API_ROOT}/v1alpha/{self._resource_prefix()}/sessions", token,
            {"displayName": "Cline Proxy Session"}
        )
        return data.get("name")

    def _stream_assist(self, token: str, session: str, agent_id: str, prompt: str) -> list[dict[str, Any]]:
        url = f"{DISCOVERY_API_ROOT}/v1alpha/{self._resource_prefix()}/assistants/{self.assistant}:streamAssist"
        payload = {
            "session": session,
            "query": {"parts": [{"text": prompt}]},
            "agentsConfig": {"agent": agent_id},
            "agentsSpec": {"agentSpecs": [{"agentId": agent_id, "version": self.agent_version}]},
            "answerGenerationMode": "AGENT",
            "assistSkippingMode": "REQUEST_ASSIST",
            "languageCode": self.language_code,
            "userMetadata": {"timeZone": self.time_zone},
        }
        response = self._post_json(url, token, payload, stream=True)
        
        decoder, buffer = json.JSONDecoder(), ""
        events = []
        for chunk in response.iter_content():
            buffer += chunk
            while True:
                buffer = buffer.lstrip()
                if not buffer: break
                if buffer[0] in "[,]":
                    buffer = buffer[1:]
                    continue
                try:
                    obj, index = decoder.raw_decode(buffer)
                    events.append(obj)
                    buffer = buffer[index:]
                except json.JSONDecodeError:
                    break
        return events

    @staticmethod
    def _collect_answer_text(events: list[dict[str, Any]]) -> str:
        parts = []
        for event in events:
            replies = event.get("answer", {}).get("replies") if isinstance(event.get("answer"), dict) else None
            if not isinstance(replies, list): continue
            for reply in replies:
                content = reply.get("groundedContent", {}).get("content") if isinstance(reply, dict) else None
                if isinstance(content, dict) and content.get("thought") is not True:
                    text = content.get("text")
                    if isinstance(text, str): parts.append(text)
        return "".join(parts)

    @staticmethod
    def _try_extract_json(text: str) -> Any:
        decoder = json.JSONDecoder()
        for i, char in enumerate(text):
            if char in "{[":
                try: return decoder.raw_decode(text[i:])[0]
                except json.JSONDecodeError: continue
        return None

# Instantiate the backend globally
BACKEND = GeminiEnterpriseBackend()

# =============================================================================
# FASTAPI PROXY (CLINE INTEGRATION)
# =============================================================================

app = FastAPI()

def gemini_sse(payload: dict):
    """Return one valid Gemini SSE JSON event. Gemini does not use data: [DONE]."""
    def gen():
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def build_text_response(text: str):
    return {
        "candidates": [{
            "content": {"role": "model", "parts": [{"text": text}]},
            "finishReason": "STOP",
            "index": 0,
        }]
    }


def build_function_call(name: str, args: dict):
    """Return only the Gemini functionCall part, without extra text."""
    return {
        "candidates": [{
            "content": {
                "role": "model",
                "parts": [{"functionCall": {"name": name, "args": args}}],
            },
            "finishReason": "STOP",
            "index": 0,
        }]
    }


def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def get_function_declarations(tools: list) -> list[dict]:
    declarations = []
    for tool_group in tools:
        if not isinstance(tool_group, dict):
            continue
        items = tool_group.get("functionDeclarations", [])
        if isinstance(items, list):
            declarations.extend(x for x in items if isinstance(x, dict))
    return declarations


def parse_tool_call(text: str) -> dict | None:
    """Extract only a valid {name, args} tool-call object."""
    cleaned = clean_json_response(text)
    candidates = [cleaned]

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char in "{[":
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
                candidates.append(value)
                break
            except json.JSONDecodeError:
                continue

    for value in candidates:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                continue
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if isinstance(value, dict) and isinstance(value.get("name"), str) and isinstance(value.get("args"), dict):
            return value
    return None


def validate_tool_call(call: dict, declarations: list[dict]) -> tuple[bool, str]:
    by_name = {item.get("name"): item for item in declarations if item.get("name")}
    name = call.get("name")
    if name not in by_name:
        return False, f"Unknown tool '{name}'. Allowed tools: {', '.join(by_name)}"

    schema = by_name[name].get("parameters", {})
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [key for key in required if key not in call.get("args", {})]
    if missing:
        return False, f"Tool '{name}' is missing required arguments: {', '.join(missing)}"
    return True, ""


def request_needs_tool(user_prompt: str) -> bool:
    """Identify tasks that must change/read the local workspace."""
    return bool(re.search(
        r"\b(create|save|write|edit|modify|update|delete|remove|rename|move|copy|"
        r"run|execute|test|read|inspect|open|search|find|list|generate|build)\b",
        user_prompt,
        flags=re.IGNORECASE,
    ))


@app.post("/{path:path}")
async def handle_cline_request(path: str, request: FastAPIRequest):
    body = await request.json()
    contents = body.get("contents", [])
    tools = body.get("tools", [])
    declarations = get_function_declarations(tools)

    

    is_tool_response = False
    tool_data = None
    if contents:
        for part in contents[-1].get("parts", []):
            if isinstance(part, dict) and "functionResponse" in part:
                is_tool_response = True
                tool_data = part["functionResponse"]
                break

    if is_tool_response:
        tool_name = tool_data.get("name", "unknown")
        tool_result = tool_data.get("response", {})
        user_prompt = (
            f"The Cline tool '{tool_name}' executed locally.\n"
            f"Tool result: {json.dumps(tool_result, ensure_ascii=False)}\n"
            "If another local action is required, return exactly one JSON tool call. "
            "Otherwise, return a short completion summary."
        )
        must_call_tool = False
    else:
        user_prompt = next(
            (
                part["text"]
                for message in reversed(contents)
                if message.get("role") == "user"
                for part in message.get("parts", [])
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ),
            "",
        )
        must_call_tool = bool(declarations) and request_needs_tool(user_prompt)

    if not user_prompt:
        return gemini_sse(build_text_response("No text prompt detected."))

    tool_names = [item.get("name") for item in declarations if item.get("name")]
    system_prompt = ""
    if declarations:
        system_prompt = (
            "You are the reasoning backend for Cline in VS Code. Cline executes local tools.\n"
            f"Available tool schemas:\n{json.dumps(declarations, ensure_ascii=False)}\n\n"
            "When a local action is needed, respond ONLY with exactly one raw JSON object:\n"
            '{"name":"exact_tool_name","args":{"required_parameter":"value"}}\n'
            f"Use only these exact tool names: {', '.join(tool_names)}.\n"
            "Arguments must match the selected tool schema exactly.\n"
            "For file creation or modification, you MUST call the appropriate file-writing tool.\n"
            "Never claim that a file was created, saved, updated, executed, or tested unless the corresponding "
            "tool has successfully returned a functionResponse.\n"
            "Do not wrap a tool call in markdown and do not add explanatory text around it.\n\n"
        )

    full_prompt = system_prompt + f"Current request or tool result:\n{user_prompt}"
    retry_feedback = ""
    last_reply = ""

    try:
        for attempt in range(3):
            prompt = full_prompt + retry_feedback
            api_result = BACKEND.chat(prompt=prompt)
            last_reply = api_result.get("response", "")
            parsed = api_result.get("parsed_json")

            if isinstance(parsed, list) and len(parsed) == 1:
                parsed = parsed[0]
            if not (isinstance(parsed, dict) and "name" in parsed and "args" in parsed):
                parsed = parse_tool_call(last_reply)

            if isinstance(parsed, dict):
                valid, validation_error = validate_tool_call(parsed, declarations)
                if valid:
                    return gemini_sse(build_function_call(parsed["name"], parsed["args"]))
                retry_feedback = (
                    f"\n\nYour previous tool call was invalid: {validation_error}. "
                    "Return one corrected raw JSON tool call only."
                )
                continue

            if not must_call_tool:
                return gemini_sse(build_text_response(last_reply))

            retry_feedback = (
                "\n\nYour previous response incorrectly returned text. This request requires a local Cline tool. "
                "Do not describe proposed content and do not claim completion. "
                "Return exactly one valid raw JSON tool call using an available schema."
            )

        error_text = (
            "The agent failed to produce a valid Cline tool call after 3 attempts. "
            f"Available tools: {', '.join(tool_names) or 'none'}."
        )
        return gemini_sse(build_text_response(error_text))

    except Exception as exc:
        return gemini_sse(build_text_response(f"Proxy error: {exc}"))


if __name__ == "__main__":
    print("Initializing Enterprise Backend...")
    BACKEND.initialize()
    print("Starting Cline Proxy on http://localhost:4000")
    uvicorn.run(app, host="127.0.0.1", port=4000)
