from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
from decimal import Decimal

import pandas as pd
import boto3
import math
import tempfile
import os
import subprocess

from openmp_processor import run_openmp


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Air Quality API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AWS CONFIGURATION
# ============================================================

AWS_REGION = "ap-south-1"

LIVE_TABLE = "air-quality-live"
HISTORY_TABLE = "air-quality-history"


# ============================================================
# AWS CLIENTS
# ============================================================

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION
)

live_table = dynamodb.Table(LIVE_TABLE)
history_table = dynamodb.Table(HISTORY_TABLE)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

DATA_DIR = PROJECT_DIR / "data"

PROCESSED_DIR = DATA_DIR / "processed"

LIVE_DIR = DATA_DIR / "live"

CLEAN_FILE = (
    PROCESSED_DIR /
    "air_quality_cleaned.csv"
)

LIVE_FILE = (
    LIVE_DIR /
    "live_air_quality.csv"
)


# ============================================================
# HPC EXECUTABLES
# ============================================================

SEQUENTIAL_EXECUTABLE = (
    PROJECT_DIR /
    "sequential_air_quality"
)

OPENMP_EXECUTABLE = (
    PROJECT_DIR /
    "openmp_air_quality"
)

MPI_EXECUTABLE = (
    PROJECT_DIR /
    "mpi_air_quality"
)

MPI_PROCESSES = 2



# ============================================================
# VALUE CONVERSION
# ============================================================

def convert_value(value):

    if isinstance(value, Decimal):

        if value % 1 == 0:
            return int(value)

        return float(value)

    if isinstance(value, float):

        if math.isnan(value) or math.isinf(value):
            return None

    return value


# ============================================================
# DYNAMODB ITEM CLEANING
# ============================================================

def clean_item(item):

    return {
        key: convert_value(value)
        for key, value in item.items()
    }


# ============================================================
# DATAFRAME -> JSON RECORDS
# ============================================================

def dataframe_to_records(df):

    records = []

    for record in df.to_dict(
        orient="records"
    ):

        cleaned = {}

        for key, value in record.items():

            if pd.isna(value):

                cleaned[key] = None

            else:

                cleaned[key] = convert_value(
                    value
                )

        records.append(cleaned)

    return records


# ============================================================
# READ PROCESSED CSV
# ============================================================

def read_clean():

    if not CLEAN_FILE.exists():

        return pd.DataFrame()

    try:

        return pd.read_csv(
            CLEAN_FILE
        )

    except Exception as e:

        print(
            "Processed CSV read error:",
            str(e)
        )

        return pd.DataFrame()


# ============================================================
# READ LOCAL LIVE CSV
# ============================================================

def read_live():

    if not LIVE_FILE.exists():

        return pd.DataFrame()

    try:

        return pd.read_csv(
            LIVE_FILE
        )

    except Exception as e:

        print(
            "Live CSV read error:",
            str(e)
        )

        return pd.DataFrame()


# ============================================================
# GET LIVE DATA FROM DYNAMODB
# ============================================================

def get_live_items():

    items = []

    try:

        response = live_table.scan()

        items.extend(
            response.get(
                "Items",
                []
            )
        )

        while "LastEvaluatedKey" in response:

            response = live_table.scan(
                ExclusiveStartKey=
                response[
                    "LastEvaluatedKey"
                ]
            )

            items.extend(
                response.get(
                    "Items",
                    []
                )
            )

    except Exception as e:

        print(
            "DynamoDB live scan error:",
            str(e)
        )

    return [
        clean_item(item)
        for item in items
    ]


# ============================================================
# GET HISTORY DATA FROM DYNAMODB
# ============================================================

def get_history_items(limit=None):

    items = []

    try:

        response = history_table.scan()

        items.extend(
            response.get(
                "Items",
                []
            )
        )

        while "LastEvaluatedKey" in response:

            response = history_table.scan(
                ExclusiveStartKey=
                response[
                    "LastEvaluatedKey"
                ]
            )

            items.extend(
                response.get(
                    "Items",
                    []
                )
            )

            if limit is not None:

                if len(items) >= limit:
                    break

    except Exception as e:

        print(
            "DynamoDB history scan error:",
            str(e)
        )

    items = [
        clean_item(item)
        for item in items
    ]

    if limit is not None:

        items = items[:limit]

    return items


# ============================================================
# MERGE PROCESSED DATA + LIVE DYNAMODB DATA
# ============================================================

def merge_station_data():

    base_df = read_clean()

    if base_df.empty:

        return pd.DataFrame()

    live_items = get_live_items()

    if not live_items:

        return base_df

    live_df = pd.DataFrame(
        live_items
    )

    if live_df.empty:

        return base_df

    base_df = base_df.copy()
    live_df = live_df.copy()

    base_df.columns = [
        str(column).strip()
        for column in base_df.columns
    ]

    live_df.columns = [
        str(column).strip()
        for column in live_df.columns
    ]

    if "station" not in base_df.columns:

        return base_df

    if "station" not in live_df.columns:

        return base_df

    possible_columns = [
        "aqi",
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "o3",
        "nh3",
        "last_update",
        "timestamp"
    ]

    live_columns = [
        column
        for column in possible_columns
        if column in live_df.columns
    ]

    if not live_columns:

        return base_df

    # --------------------------------------------------------
    # Select latest live record per station
    # --------------------------------------------------------

    if "timestamp" in live_df.columns:

        live_df["_sort_timestamp"] = pd.to_datetime(
            live_df["timestamp"],
            errors="coerce"
        )

        live_df = (
            live_df
            .sort_values(
                "_sort_timestamp"
            )
            .drop_duplicates(
                subset=["station"],
                keep="last"
            )
        )

    else:

        live_df = (
            live_df
            .drop_duplicates(
                subset=["station"],
                keep="last"
            )
        )

    live_subset = live_df[
        ["station"] + live_columns
    ].copy()

    # --------------------------------------------------------
    # Rename overlapping columns
    # --------------------------------------------------------

    rename_map = {}

    for column in live_columns:

        if column in base_df.columns:

            rename_map[column] = (
                f"{column}_live"
            )

    live_subset = live_subset.rename(
        columns=rename_map
    )

    # --------------------------------------------------------
    # Merge
    # --------------------------------------------------------

    merged = base_df.merge(
        live_subset,
        on="station",
        how="left"
    )

    # --------------------------------------------------------
    # Overlay live values
    # --------------------------------------------------------

    for column in live_columns:

        if column not in base_df.columns:

            continue

        live_column = (
            f"{column}_live"
        )

        if live_column not in merged.columns:

            continue

        merged[column] = (
            merged[live_column]
            .combine_first(
                merged[column]
            )
        )

        merged.drop(
            columns=[live_column],
            inplace=True
        )

    return merged


# ============================================================
# CREATE TEMPORARY HPC SNAPSHOT
# ============================================================

def create_hpc_snapshot():

    merged_df = merge_station_data()

    if merged_df.empty:

        return None

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        delete=False,
        encoding="utf-8"
    )

    temp_path = temp_file.name

    temp_file.close()

    merged_df.to_csv(
        temp_path,
        index=False
    )

    return temp_path


# ============================================================
# PARSE HPC OUTPUT
# ============================================================

def parse_hpc_output(output):

    data = {}

    for line in output.splitlines():

        line = line.strip()

        if "=" not in line:

            continue

        key, value = line.split(
            "=",
            1
        )

        data[key.strip()] = value.strip()

    return data


# ============================================================
# RUN HPC EXECUTABLE
# ============================================================

def run_hpc_executable(
    executable,
    csv_file
):

    if not executable.exists():

        raise FileNotFoundError(
            f"Executable not found: {executable}"
        )

    result = subprocess.run(
        [
            str(executable),
            str(csv_file)
        ],
        capture_output=True,
        text=True,
        timeout=120
    )

    if result.returncode != 0:

        error_message = (
            result.stderr.strip()
            or
            result.stdout.strip()
            or
            (
                "Executable returned "
                f"exit code {result.returncode}"
            )
        )

        raise RuntimeError(
            error_message
        )

    parsed = parse_hpc_output(
        result.stdout
    )

    return parsed


# ============================================================
# VALIDATE AND CONVERT HPC RESULT
# ============================================================

def convert_hpc_result(parsed):

    required_fields = [
        "threads",
        "records",
        "average_aqi",
        "minimum_aqi",
        "maximum_aqi",
        "execution_time"
    ]

    missing = []

    for field in required_fields:

        if field not in parsed:

            missing.append(field)

    if missing:

        raise RuntimeError(
            "Missing HPC output fields: "
            +
            ", ".join(missing)
        )

    return {

        "threads": int(
            parsed["threads"]
        ),

        "records": int(
            parsed["records"]
        ),

        "average_aqi": float(
            parsed["average_aqi"]
        ),

        "minimum_aqi": float(
            parsed["minimum_aqi"]
        ),

        "maximum_aqi": float(
            parsed["maximum_aqi"]
        ),

        "execution_time_seconds": float(
            parsed["execution_time"]
        )
    }


# ============================================================
# ROOT ENDPOINT
# ============================================================

def run_mpi(csv_file, processes=MPI_PROCESSES):
    command = [
        "mpirun",
        "--map-by",
        ":OVERSUBSCRIBE",
        "-np",
        str(processes),
        str(MPI_EXECUTABLE),
        str(csv_file),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "MPI execution failed: "
            + result.stderr.strip()
        )

    return parse_hpc_output(result.stdout)


@app.get("/")
def root():

    return {

        "status": "online",

        "service":
            "Air Quality API",

        "version":
            "1.0.0",

        "region":
            AWS_REGION,

        "live_table":
            LIVE_TABLE,

        "history_table":
            HISTORY_TABLE
    }


# ============================================================
# CURRENT AIR QUALITY
# ============================================================

@app.get(
    "/api/air-quality/current"
)
def current_air_quality():

    items = get_live_items()

    if items:

        return {

            "status":
                "success",

            "source":
                "DynamoDB",

            "records":
                items
        }

    df = read_clean()

    if df.empty:

        return {

            "status":
                "success",

            "source":
                "none",

            "records":
                []
        }

    return {

        "status":
            "success",

        "source":
            "processed_csv",

        "records":
            dataframe_to_records(df)
    }


# ============================================================
# STATIONS
# ============================================================

@app.get(
    "/api/air-quality/stations"
)
def air_quality_stations():

    df = merge_station_data()

    if df.empty:

        return {

            "status":
                "success",

            "count":
                0,

            "stations":
                []
        }

    return {

        "status":
            "success",

        "count":
            len(df),

        "stations":
            dataframe_to_records(df)
    }


# ============================================================
# HISTORY
# ============================================================

@app.get(
    "/api/air-quality/history"
)
def air_quality_history():

    items = get_history_items()

    return {

        "status":
            "success",

        "count":
            len(items),

        "history":
            items
    }


# ============================================================
# ALERTS
# ============================================================

@app.get(
    "/api/air-quality/alerts"
)
def air_quality_alerts():

    df = merge_station_data()

    if df.empty:

        return {

            "status":
                "success",

            "count":
                0,

            "alerts":
                []
        }

    if "aqi" not in df.columns:

        return {

            "status":
                "success",

            "count":
                0,

            "alerts":
                []
        }

    df["aqi"] = pd.to_numeric(
        df["aqi"],
        errors="coerce"
    )

    alerts_df = df[
        df["aqi"] > 200
    ].copy()

    alerts_df = alerts_df.sort_values(
        "aqi",
        ascending=False
    )

    alerts = dataframe_to_records(
        alerts_df
    )

    return {

        "status":
            "success",

        "count":
            len(alerts),

        "alerts":
            alerts
    }


# ============================================================
# HPC OPENMP PROCESSING
# ============================================================

@app.get(
    "/api/hpc"
)
def hpc_processing():

    temp_path = None

    try:

        temp_path = (
            create_hpc_snapshot()
        )

        if temp_path is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    "No air-quality data "
                    "available for HPC processing"
                )
            )

        result = run_openmp(
            temp_path
        )

        return {

            "status":
                "success",

            **result
        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "HPC processing failed: "
                + str(e)
            )
        )

    finally:

        if temp_path:

            try:

                os.remove(
                    temp_path
                )

            except OSError:

                pass


# ============================================================
# HPC SEQUENTIAL VS OPENMP
# ============================================================

@app.get(
    "/api/hpc/compare"
)
def hpc_compare():

    if not CLEAN_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Processed dataset not found: "
                + str(CLEAN_FILE)
            )
        )

    if not SEQUENTIAL_EXECUTABLE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Sequential executable not found: "
                + str(SEQUENTIAL_EXECUTABLE)
            )
        )

    if not OPENMP_EXECUTABLE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "OpenMP executable not found: "
                + str(OPENMP_EXECUTABLE)
            )
        )

    if not MPI_EXECUTABLE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "MPI executable not found: "
                + str(MPI_EXECUTABLE)
            )
        )

    try:

        # ====================================================
        # SEQUENTIAL
        # ====================================================

        sequential_raw = run_hpc_executable(
            SEQUENTIAL_EXECUTABLE,
            CLEAN_FILE
        )

        sequential = convert_hpc_result(
            sequential_raw
        )

        # ====================================================
        # OPENMP
        # ====================================================

        openmp_raw = run_hpc_executable(
            OPENMP_EXECUTABLE,
            CLEAN_FILE
        )

        openmp = convert_hpc_result(
            openmp_raw
        )

        # ====================================================
        # MPI
        # ====================================================

        mpi_raw = run_mpi(
            CLEAN_FILE,
            MPI_PROCESSES
        )

        mpi = {
            "processes": int(mpi_raw["processes"]),
            "records": int(mpi_raw["records"]),
            "average_aqi": float(mpi_raw["average_aqi"]),
            "minimum_aqi": float(mpi_raw["minimum_aqi"]),
            "maximum_aqi": float(mpi_raw["maximum_aqi"]),
            "execution_time_seconds": float(
                mpi_raw["execution_time"]
            )
        }

        # ====================================================
        # VERIFY SAME WORKLOAD
        # ====================================================

        if (
            sequential["records"]
            != openmp["records"]
            or
            sequential["records"]
            != mpi["records"]
        ):
            raise RuntimeError(
                "Sequential, OpenMP and MPI processed "
                "different numbers of records."
            )

        # ====================================================
        # OPENMP RESULT CHECK
        # ====================================================

        openmp_average_difference = abs(
            sequential["average_aqi"]
            - openmp["average_aqi"]
        )

        openmp_minimum_difference = abs(
            sequential["minimum_aqi"]
            - openmp["minimum_aqi"]
        )

        openmp_maximum_difference = abs(
            sequential["maximum_aqi"]
            - openmp["maximum_aqi"]
        )

        openmp_results_match = (
            openmp_average_difference < 0.01
            and
            openmp_minimum_difference < 0.01
            and
            openmp_maximum_difference < 0.01
        )

        # ====================================================
        # MPI RESULT CHECK
        # ====================================================

        mpi_average_difference = abs(
            sequential["average_aqi"]
            - mpi["average_aqi"]
        )

        mpi_minimum_difference = abs(
            sequential["minimum_aqi"]
            - mpi["minimum_aqi"]
        )

        mpi_maximum_difference = abs(
            sequential["maximum_aqi"]
            - mpi["maximum_aqi"]
        )

        mpi_results_match = (
            mpi_average_difference < 0.01
            and
            mpi_minimum_difference < 0.01
            and
            mpi_maximum_difference < 0.01
        )

        # ====================================================
        # SPEEDUP
        # ====================================================

        sequential_time = sequential[
            "execution_time_seconds"
        ]

        openmp_time = openmp[
            "execution_time_seconds"
        ]

        mpi_time = mpi[
            "execution_time_seconds"
        ]

        openmp_speedup = (
            sequential_time / openmp_time
            if openmp_time > 0
            else None
        )

        mpi_speedup = (
            sequential_time / mpi_time
            if mpi_time > 0
            else None
        )

        # ====================================================
        # EFFICIENCY
        # ====================================================

        openmp_threads = openmp["threads"]
        mpi_processes = mpi["processes"]

        openmp_efficiency = (
            (
                openmp_speedup
                / openmp_threads
            ) * 100.0
            if openmp_speedup is not None
            and openmp_threads > 0
            else None
        )

        mpi_efficiency = (
            (
                mpi_speedup
                / mpi_processes
            ) * 100.0
            if mpi_speedup is not None
            and mpi_processes > 0
            else None
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return {
            "status": "success",

            "framework": "Sequential vs OpenMP vs MPI",

            "workload": {
                "dataset": CLEAN_FILE.name,
                "records": sequential["records"]
            },

            "sequential": {
                "threads": sequential["threads"],
                "records": sequential["records"],
                "average_aqi": sequential["average_aqi"],
                "minimum_aqi": sequential["minimum_aqi"],
                "maximum_aqi": sequential["maximum_aqi"],
                "execution_time_seconds":
                    sequential["execution_time_seconds"]
            },

            "openmp": {
                "threads": openmp["threads"],
                "records": openmp["records"],
                "average_aqi": openmp["average_aqi"],
                "minimum_aqi": openmp["minimum_aqi"],
                "maximum_aqi": openmp["maximum_aqi"],
                "execution_time_seconds":
                    openmp["execution_time_seconds"]
            },

            "mpi": {
                "processes": mpi["processes"],
                "records": mpi["records"],
                "average_aqi": mpi["average_aqi"],
                "minimum_aqi": mpi["minimum_aqi"],
                "maximum_aqi": mpi["maximum_aqi"],
                "execution_time_seconds":
                    mpi["execution_time_seconds"]
            },

            "comparison": {
                "openmp_speedup": openmp_speedup,
                "mpi_speedup": mpi_speedup,

                "openmp_efficiency_percent":
                    openmp_efficiency,

                "mpi_efficiency_percent":
                    mpi_efficiency,

                "openmp_average_aqi_difference":
                    openmp_average_difference,

                "openmp_minimum_aqi_difference":
                    openmp_minimum_difference,

                "openmp_maximum_aqi_difference":
                    openmp_maximum_difference,

                "mpi_average_aqi_difference":
                    mpi_average_difference,

                "mpi_minimum_aqi_difference":
                    mpi_minimum_difference,

                "mpi_maximum_aqi_difference":
                    mpi_maximum_difference,

                "openmp_results_match":
                    openmp_results_match,

                "mpi_results_match":
                    mpi_results_match,

                "all_results_match":
                    (
                        openmp_results_match
                        and mpi_results_match
                    )
            }
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get(
    "/api/stats"
)
def stats():

    df = merge_station_data()

    total_stations = 0

    average_aqi = None

    stations_with_alerts = 0

    # --------------------------------------------------------
    # Station statistics
    # --------------------------------------------------------

    if not df.empty:

        if "station" in df.columns:

            total_stations = (
                df["station"]
                .nunique()
            )

        if "aqi" in df.columns:

            df["aqi"] = pd.to_numeric(
                df["aqi"],
                errors="coerce"
            )

            valid_aqi = (
                df["aqi"]
                .dropna()
            )

            if not valid_aqi.empty:

                average_aqi = float(
                    valid_aqi.mean()
                )

                stations_with_alerts = int(
                    (
                        valid_aqi > 200
                    ).sum()
                )

    # --------------------------------------------------------
    # History records
    # --------------------------------------------------------

    history_items = (
        get_history_items()
    )

    data_records = len(
        history_items
    )

    # --------------------------------------------------------
    # OpenMP statistics
    # --------------------------------------------------------

    hpc_result = None

    temp_path = None

    try:

        temp_path = (
            create_hpc_snapshot()
        )

        if temp_path:

            hpc_result = (
                run_openmp(
                    temp_path
                )
            )

    except Exception as e:

        print(
            "OpenMP statistics error:",
            str(e)
        )

    finally:

        if temp_path:

            try:

                os.remove(
                    temp_path
                )

            except OSError:

                pass

    # --------------------------------------------------------
    # Use actual OpenMP average
    # --------------------------------------------------------

    if hpc_result:

        if "average_aqi" in hpc_result:

            try:

                average_aqi = float(
                    hpc_result[
                        "average_aqi"
                    ]
                )

            except (
                ValueError,
                TypeError
            ):

                pass

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "status":
            "success",

        "average_aqi":
            average_aqi,

        "total_stations":
            total_stations,

        "stations_with_alerts":
            stations_with_alerts,

        "data_records":
            data_records,

        "hpc":
            hpc_result
    }


# ============================================================
# LEGACY LIVE ENDPOINT
# ============================================================

@app.get(
    "/api/live"
)
def legacy_live():

    items = get_live_items()

    return {

        "status":
            "success",

        "count":
            len(items),

        "data":
            items
    }


# ============================================================
# LEGACY STATIONS ENDPOINT
# ============================================================

@app.get(
    "/api/stations"
)
def legacy_stations():

    df = merge_station_data()

    if df.empty:

        return {

            "status":
                "success",

            "count":
                0,

            "data":
                []
        }

    records = dataframe_to_records(
        df
    )

    return {

        "status":
            "success",

        "count":
            len(records),

        "data":
            records
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
