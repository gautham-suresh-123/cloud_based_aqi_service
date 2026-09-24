import subprocess


OPENMP_EXECUTABLE = "./openmp_air_quality"


def run_openmp(csv_file):

    result = subprocess.run(
        [
            OPENMP_EXECUTABLE,
            csv_file
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stdout or result.stderr
        )

    output = result.stdout

    data = {}

    for line in output.splitlines():

        if "=" in line:

            key, value = line.split(
                "=",
                1
            )

            data[key.strip()] = value.strip()

    if "threads" not in data:

        raise RuntimeError(
            "Invalid OpenMP output"
        )

    return {
        "framework": "OpenMP",
        "threads": int(
            data["threads"]
        ),
        "records_processed": int(
            data["records"]
        ),
        "average_aqi": float(
            data["average_aqi"]
        ),
        "minimum_aqi": float(
            data["minimum_aqi"]
        ),
        "maximum_aqi": float(
            data["maximum_aqi"]
        ),
        "execution_time_seconds": float(
            data["execution_time"]
        )
    }
