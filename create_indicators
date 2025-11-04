import pandas as pd
import numpy as np
from pandas.tseries.offsets import BDay
import os

# Define file paths relative to script location
input_file = "stock_data_last_2_days.csv"
output_file = "stock_data_with_indicators.csv"

# Load the CSV file
df = pd.read_csv(input_file, parse_dates=["Date"])

# Sort by Ticker and Date
df.sort_values(by=["Ticker", "Date"], inplace=True)

# Generate 26 future business days per ticker
future_days = 26
tickers = df["Ticker"].unique()
latest_date = df["Date"].max()
future_dates = pd.date_range(start=latest_date + BDay(1), periods=future_days, freq=BDay())
future_rows = pd.DataFrame([(date, ticker) for ticker in tickers for date in future_dates], columns=["Date", "Ticker"])
for col in ["Open", "High", "Low", "Close", "Volume"]:
    future_rows[col] = np.nan

# Append future rows
df_extended = pd.concat([df, future_rows], ignore_index=True)
df_extended.sort_values(by=["Ticker", "Date"], inplace=True)

# Compute indicators
def compute_indicators(group):
    group = group.copy()
    group["SMA_22"] = group["Close"].rolling(window=22, min_periods=1).mean()
    group["STD_22"] = group["Close"].rolling(window=22, min_periods=1).std()
    group["BB_Upper"] = group["SMA_22"] + 2 * group["STD_22"]
    group["BB_Lower"] = group["SMA_22"] - 2 * group["STD_22"]

    group["BB_Flag"] = np.where(
        (group[["Close", "Open"]].max(axis=1) > group["BB_Upper"]),
        "BBH",
        np.where(
            (group[["Close", "Open"]].min(axis=1) < group["BB_Lower"]),
            "BBL",
            np.nan
        )
    )
    group.loc[group[["Close", "Open", "BB_Upper", "BB_Lower"]].isnull().any(axis=1), "BB_Flag"] = np.nan

    delta = group["Close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=14, min_periods=1).mean()
    avg_loss = pd.Series(loss).rolling(window=14, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    group["RSI_14"] = rsi.where(np.isfinite(rsi), np.nan)

    conv_line = (group["High"].rolling(window=9, min_periods=1).max() + group["Low"].rolling(window=9, min_periods=1).min()) / 2
    base_line = (group["High"].rolling(window=26, min_periods=1).max() + group["Low"].rolling(window=26, min_periods=1).min()) / 2
    group["Senkou_Span_A"] = ((conv_line + base_line) / 2).shift(26)
    span_b = (group["High"].rolling(window=52, min_periods=1).max() + group["Low"].rolling(window=52, min_periods=1).min()) / 2
    group["Senkou_Span_B"] = span_b.shift(26)

    return group

df_final = df_extended.groupby("Ticker", group_keys=False).apply(compute_indicators)

# Save to CSV in the same repo location
df_final.to_csv(output_file, index=False)
