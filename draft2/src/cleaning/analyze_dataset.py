from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_DIR / "data" / "raw" / "CITY_DATA.csv"

if not DATA_FILE.exists():
    print("Dataset not found:")
    print(DATA_FILE)
    exit()

df = pd.read_csv(DATA_FILE)

print("\n" + "=" * 60)
print("AIR QUALITY DATASET ANALYSIS")
print("=" * 60)

print("\nDataset Shape:")
print("Rows:", df.shape[0])
print("Columns:", df.shape[1])

print("\nColumns:")
print(list(df.columns))

print("\nData Types:")
print(df.dtypes)

print("\nMissing Values:")
print(df.isnull().sum())

print("\nDuplicate Records:")
print(df.duplicated().sum())

print("\nStates:", df["state"].nunique())
print("Cities:", df["city"].nunique())
print("Stations:", df["station"].nunique())

print("\nPollutants:")
print(df["pollutant_id"].value_counts())

df["last_update"] = pd.to_datetime(
    df["last_update"],
    dayfirst=True,
    errors="coerce"
)

print("\nTimestamp:")
print("From:", df["last_update"].min())
print("To  :", df["last_update"].max())

print("\nPollutant Statistics:")
print(
    df.groupby("pollutant_id")["pollutant_avg"]
    .agg(["count", "min", "max", "mean"])
    .round(2)
)

print("\nStations per City:")
print(
    df.groupby("city")["station"]
    .nunique()
    .sort_values(ascending=False)
)

print("\nFirst 10 Records:")
print(df.head(10).to_string(index=False))

print("\n" + "=" * 60)
print("ANALYSIS COMPLETED")
print("=" * 60)