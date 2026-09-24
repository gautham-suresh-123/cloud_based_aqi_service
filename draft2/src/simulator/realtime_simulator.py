import pandas as pd
import random
import time
import os
import boto3
from decimal import Decimal
from datetime import datetime

PROJECT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

INPUT_FILE = os.path.join(
    PROJECT_DIR,
    "data",
    "processed",
    "air_quality_cleaned.csv"
)

LIVE_FILE = os.path.join(
    PROJECT_DIR,
    "data",
    "live",
    "live_air_quality.csv"
)

REGION = "ap-south-1"

LIVE_TABLE = "air-quality-live"
HISTORY_TABLE = "air-quality-history"

POLLUTANTS = [
    "pm25",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",
    "nh3"
]

df = pd.read_csv(INPUT_FILE)

df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")

for col in POLLUTANTS:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df[df["aqi"].notna()].copy()

os.makedirs(os.path.dirname(LIVE_FILE), exist_ok=True)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=REGION
)

live_table = dynamodb.Table(LIVE_TABLE)
history_table = dynamodb.Table(HISTORY_TABLE)

print("=" * 60)
print("REAL-TIME AIR QUALITY SIMULATOR")
print("=" * 60)
print(f"Stations loaded: {len(df)}")
print(f"Live DynamoDB table: {LIVE_TABLE}")
print(f"History DynamoDB table: {HISTORY_TABLE}")
print("Starting simulation...")
print()

while True:

    station = df.sample(1).iloc[0]

    reading = station.to_dict()

    timestamp = datetime.now().strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )

    aqi = min(
        500,
        max(
            0,
            int(
                float(reading["aqi"]) *
                random.uniform(0.95, 1.05)
            )
        )
    )

    output = {
        "last_update": str(reading.get("last_update", "")),
        "station": str(reading["station"]),
        "city": str(reading["city"]),
        "state": str(reading["state"]),
        "latitude": Decimal(str(round(float(reading["latitude"]), 6))),
        "longitude": Decimal(str(round(float(reading["longitude"]), 6))),
        "aqi": aqi,
        "timestamp": timestamp
    }

    for pollutant in POLLUTANTS:
        value = reading[pollutant]

        if pd.notna(value):
            value = float(value)
            value = value * random.uniform(0.90, 1.10)
            output[pollutant] = Decimal(
                str(round(max(0, value), 2))
            )

    # Latest reading
    live_table.put_item(
        Item=output
    )

    # Historical reading
    history_table.put_item(
        Item=output
    )

    # Local backup
    csv_output = {
        k: float(v) if isinstance(v, Decimal) else v
        for k, v in output.items()
    }

    file_exists = os.path.exists(LIVE_FILE)

    pd.DataFrame([csv_output]).to_csv(
        LIVE_FILE,
        mode="a",
        header=not file_exists,
        index=False
    )

    pm25_display = output.get("pm25", "N/A")

    print(
        f"{timestamp} | "
        f"{output['city']} | "
        f"AQI: {aqi} | "
        f"PM2.5: {pm25_display} | "
        f"DynamoDB LIVE + HISTORY OK"
    )

    time.sleep(5)