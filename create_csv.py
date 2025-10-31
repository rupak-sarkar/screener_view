import csv
from datetime import datetime
from pathlib import Path

def create_csv():
    # Save CSV in a 'data' directory
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    filename = output_dir / f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    data = [
        ["Name", "Age", "City"],
        ["Alice", 28, "New York"],
        ["Bob", 34, "Los Angeles"],
        ["Charlie", 25, "Chicago"]
    ]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)

    print(f"✅ CSV created: {filename}")

if __name__ == "__main__":
    create_csv()
