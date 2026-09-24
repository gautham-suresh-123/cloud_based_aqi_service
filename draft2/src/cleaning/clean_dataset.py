from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = PROJECT_DIR / "data" / "raw" / "CITY_DATA.csv"
OUTPUT_DIR = PROJECT_DIR / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "air_quality_cleaned.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_FILE)

df["last_update"] = pd.to_datetime(
    df["last_update"],
    dayfirst=True,
    errors="coerce"
)

pollutant_map = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "OZONE": "o3",
    "SO2": "so2",
    "NH3": "nh3",
    "NO2": "no2",
    "CO": "co"
}

df["pollutant_id"] = df["pollutant_id"].replace(pollutant_map)

df = df.dropna(subset=["pollutant_avg"])

index_columns = [
    "country",
    "state",
    "city",
    "station",
    "last_update",
    "latitude",
    "longitude"
]

df_clean = df.pivot_table(
    index=index_columns,
    columns="pollutant_id",
    values="pollutant_avg",
    aggfunc="first"
).reset_index()

df_clean.columns.name = None

pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"]

for pollutant in pollutants:
    if pollutant not in df_clean.columns:
        df_clean[pollutant] = np.nan

breakpoints = {
    "pm25": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 500, 401, 500)
    ],
    "pm10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 1000, 401, 500)
    ],
    "no2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 1000, 401, 500)
    ],
    "so2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 2000, 401, 500)
    ],
    "co": [
        (0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10, 101, 200),
        (10.1, 17, 201, 300),
        (17.1, 34, 301, 400),
        (34.1, 50, 401, 500)
    ],
    "o3": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, 1000, 401, 500)
    ],
    "nh3": [
        (0, 200, 0, 50),
        (201, 400, 51, 100),
        (401, 800, 101, 200),
        (801, 1200, 201, 300),
        (1201, 1800, 301, 400),
        (1801, 2000, 401, 500)
    ]
}


def calculate_sub_index(value, pollutant):
    if pd.isna(value):
        return np.nan

    for c_low, c_high, i_low, i_high in breakpoints[pollutant]:
        if c_low <= value <= c_high:
            index = (
                (i_high - i_low)
                / (c_high - c_low)
                * (value - c_low)
                + i_low
            )
            return round(index)

    return 500


def calculate_aqi(row):
    sub_indices = []

    for pollutant in pollutants:
        value = row[pollutant]

        if not pd.isna(value):
            sub_index = calculate_sub_index(value, pollutant)

            if not pd.isna(sub_index):
                sub_indices.append(sub_index)

    if len(sub_indices) < 3:
        return np.nan

    if pd.isna(row["pm25"]) and pd.isna(row["pm10"]):
        return np.nan

    return max(sub_indices)


df_clean["aqi"] = df_clean.apply(calculate_aqi, axis=1)

df_clean["aqi"] = df_clean["aqi"].clip(upper=500)

column_order = [
    "last_update",
    "station",
    "city",
    "state",
    "latitude",
    "longitude",
    "aqi",
    "pm25",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",
    "nh3"
]

df_clean = df_clean[column_order]

df_clean.to_csv(OUTPUT_FILE, index=False)

print("=" * 60)
print("DATA CLEANING COMPLETED")
print("=" * 60)

print("\nInput records:", len(df))
print("Cleaned stations:", len(df_clean))
print("AQI calculated:", df_clean["aqi"].notna().sum())
print("AQI unavailable:", df_clean["aqi"].isna().sum())

print("\nOutput:")
print(OUTPUT_FILE)

print("\nSample:")
print(df_clean.head(10).to_string(index=False))