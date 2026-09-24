import boto3
import requests
import time
from datetime import datetime, timezone
from decimal import Decimal

REGION = "ap-south-1"
TABLE_NAME = "air-quality-live"

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# IMPORTANT:
# Smaller batches + delay prevents 429 rate-limit errors.
BATCH_SIZE = 20
BATCH_DELAY = 5

dynamodb = boto3.resource(
    "dynamodb",
    region_name=REGION
)

table = dynamodb.Table(TABLE_NAME)


def get_all_stations():

    stations = []

    response = table.scan()

    stations.extend(
        response.get("Items", [])
    )

    while "LastEvaluatedKey" in response:

        response = table.scan(
            ExclusiveStartKey=
            response["LastEvaluatedKey"]
        )

        stations.extend(
            response.get("Items", [])
        )

    return stations


def prepare_stations(stations):

    result = []

    for station in stations:

        try:

            result.append({
                "station": station["station"],
                "city": station.get(
                    "city",
                    "Unknown"
                ),
                "state": station.get(
                    "state",
                    "Unknown"
                ),
                "latitude": float(
                    station["latitude"]
                ),
                "longitude": float(
                    station["longitude"]
                )
            })

        except Exception:

            continue

    return result


def fetch_batch(batch):

    latitude = ",".join(
        str(x["latitude"])
        for x in batch
    )

    longitude = ",".join(
        str(x["longitude"])
        for x in batch
    )

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "current": (
            "pm10,"
            "pm2_5,"
            "carbon_monoxide,"
            "nitrogen_dioxide,"
            "sulphur_dioxide,"
            "ozone,"
            "ammonia,"
            "us_aqi"
        ),

        "timezone": "Asia/Kolkata"
    }

    for attempt in range(5):

        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=60
        )

        if response.status_code == 429:

            wait_time = 30 * (
                attempt + 1
            )

            print(
                f"RATE LIMITED - "
                f"waiting {wait_time}s"
            )

            time.sleep(wait_time)

            continue

        response.raise_for_status()

        return response.json()

    raise RuntimeError(
        "Open-Meteo rate limit persisted "
        "after 5 retries"
    )


def update_station(station, data):

    current = data.get(
        "current",
        {}
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    item = {

        "station":
            station["station"],

        "city":
            station["city"],

        "state":
            station["state"],

        "latitude":
            Decimal(
                str(station["latitude"])
            ),

        "longitude":
            Decimal(
                str(station["longitude"])
            ),

        "pm25":
            Decimal(
                str(
                    current.get(
                        "pm2_5"
                    ) or 0
                )
            ),

        "pm10":
            Decimal(
                str(
                    current.get(
                        "pm10"
                    ) or 0
                )
            ),

        "co":
            Decimal(
                str(
                    current.get(
                        "carbon_monoxide"
                    ) or 0
                )
            ),

        "no2":
            Decimal(
                str(
                    current.get(
                        "nitrogen_dioxide"
                    ) or 0
                )
            ),

        "so2":
            Decimal(
                str(
                    current.get(
                        "sulphur_dioxide"
                    ) or 0
                )
            ),

        "o3":
            Decimal(
                str(
                    current.get(
                        "ozone"
                    ) or 0
                )
            ),

        "nh3":
            Decimal(
                str(
                    current.get(
                        "ammonia"
                    ) or 0
                )
            ),

        "aqi":
            Decimal(
                str(
                    current.get(
                        "us_aqi"
                    ) or 0
                )
            ),

        "last_update":
            current.get(
                "time",
                timestamp
            ),

        "timestamp":
            timestamp
    }

    table.put_item(
        Item=item
    )


def main():

    print(
        "======================================"
    )

    print(
        "REAL-TIME AQ COLLECTION"
    )

    print(
        "======================================"
    )

    stations = get_all_stations()

    print(
        f"Stations found: {len(stations)}"
    )

    stations = prepare_stations(
        stations
    )

    print(
        f"Valid stations: {len(stations)}"
    )

    updated = 0

    total = len(stations)

    for start in range(
        0,
        total,
        BATCH_SIZE
    ):

        batch = stations[
            start:
            start + BATCH_SIZE
        ]

        batch_number = (
            start // BATCH_SIZE
        ) + 1

        total_batches = (
            (total + BATCH_SIZE - 1)
            // BATCH_SIZE
        )

        print(
            f"\nBATCH "
            f"{batch_number}/"
            f"{total_batches} "
            f"({len(batch)} stations)"
        )

        try:

            result = fetch_batch(
                batch
            )

            if isinstance(
                result,
                list
            ):

                results = result

            else:

                results = [result]

            for station, data in zip(
                batch,
                results
            ):

                try:

                    update_station(
                        station,
                        data
                    )

                    updated += 1

                    aqi = (
                        data
                        .get(
                            "current",
                            {}
                        )
                        .get(
                            "us_aqi",
                            0
                        )
                    )

                    print(
                        f"UPDATED | "
                        f"{station['city']} | "
                        f"{station['station']} | "
                        f"AQI={aqi}"
                    )

                except Exception as e:

                    print(
                        f"UPDATE FAILED | "
                        f"{station['station']} | "
                        f"{e}"
                    )

        except Exception as e:

            print(
                f"BATCH FAILED | "
                f"{start + 1}-"
                f"{start + len(batch)} | "
                f"{e}"
            )

        # Delay between API requests
        if start + BATCH_SIZE < total:

            print(
                f"Waiting {BATCH_DELAY}s..."
            )

            time.sleep(
                BATCH_DELAY
            )

    print(
        "\n======================================"
    )

    print(
        f"UPDATED STATIONS: {updated}/{total}"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()
