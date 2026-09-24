import React, { useEffect, useState } from "react";

const API_BASE = "http://65.2.121.61:8000";

export default function HPCPerformance() {
  const [data, setData] = useState(null);

  const [stations, setStations] = useState([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ============================================================
  // LOAD ALL LIVE AIR QUALITY STATIONS
  // ============================================================

  const loadLiveStations = async () => {
    try {
      setLiveLoading(true);
      setLiveError("");

      const response = await fetch(`${API_BASE}/api/live`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Live API Error: ${response.status}`);
      }

      const result = await response.json();

      if (result.status !== "success") {
        throw new Error("Live API returned an unsuccessful response");
      }

      const stationData = Array.isArray(result.data)
        ? result.data
        : [];

      setStations(stationData);
    } catch (err) {
      console.error("Live AQ error:", err);

      setLiveError(
        err.message || "Failed to load live air quality data"
      );
    } finally {
      setLiveLoading(false);
    }
  };

  // ============================================================
  // LOAD LIVE DATA ON PAGE LOAD + EVERY 60 SECONDS
  // ============================================================

  useEffect(() => {
    loadLiveStations();

    const interval = setInterval(() => {
      loadLiveStations();
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  // ============================================================
  // HPC BENCHMARK
  // ============================================================

  const runBenchmark = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE}/api/hpc/compare`,
        {
          cache: "no-store",
        }
      );

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const result = await response.json();

      setData(result);
    } catch (err) {
      console.error("HPC benchmark error:", err);

      setError(
        err.message || "Failed to run HPC benchmark"
      );
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // AQI CLASSIFICATION
  // ============================================================

  const getAQIClass = (aqi) => {
    const value = Number(aqi);

    if (value <= 50) {
      return "bg-green-100 text-green-700";
    }

    if (value <= 100) {
      return "bg-yellow-100 text-yellow-700";
    }

    if (value <= 200) {
      return "bg-orange-100 text-orange-700";
    }

    if (value <= 300) {
      return "bg-red-100 text-red-700";
    }

    if (value <= 400) {
      return "bg-purple-100 text-purple-700";
    }

    return "bg-red-200 text-red-900";
  };

  // ============================================================
  // SORT STATIONS BY AQI
  // ============================================================

  const sortedStations = [...stations].sort(
    (a, b) => Number(b.aqi || 0) - Number(a.aqi || 0)
  );

  return (
    <div className="min-h-screen bg-[#f6f8f7] p-6">

      {/* ======================================================
          HEADER
      ====================================================== */}

      <div className="mb-6">

        <h1 className="text-3xl font-bold text-[#3b171f]">
          HPC Performance
        </h1>

        <p className="mt-1 text-gray-600">
          Real-time air quality monitoring and HPC performance
        </p>

      </div>

      {/* ======================================================
          REAL-TIME STATUS
      ====================================================== */}

      <div className="mb-6 rounded-xl bg-white p-6 shadow-sm">

        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">

          <div>

            <h2 className="text-xl font-bold text-gray-800">
              Real-Time Air Quality
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Live data from all available monitoring stations
            </p>

          </div>

          <div className="flex items-center gap-3">

            <div className="flex items-center gap-2">

              <span
                className={`h-3 w-3 rounded-full ${
                  liveLoading
                    ? "bg-yellow-400"
                    : stations.length > 0
                    ? "bg-green-500"
                    : "bg-red-500"
                }`}
              />

              <span className="text-sm font-semibold text-gray-700">

                {liveLoading
                  ? "Updating..."
                  : `${stations.length} stations loaded`}

              </span>

            </div>

            <button
              onClick={loadLiveStations}
              disabled={liveLoading}
              className="rounded-lg bg-[#7b1e2b] px-4 py-2 text-sm font-semibold text-white hover:bg-[#641823] disabled:opacity-50"
            >
              {liveLoading ? "Updating..." : "Refresh"}
            </button>

          </div>

        </div>

        {/* LIVE ERROR */}

        {liveError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
            {liveError}
          </div>
        )}

        {/* ==================================================
            LIVE SUMMARY
        ================================================== */}

        {stations.length > 0 && (

          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-4">

            <SummaryCard
              title="Total Stations"
              value={stations.length}
            />

            <SummaryCard
              title="Highest AQI"
              value={Math.max(
                ...stations.map((s) =>
                  Number(s.aqi || 0)
                )
              ).toFixed(0)}
            />

            <SummaryCard
              title="Lowest AQI"
              value={Math.min(
                ...stations.map((s) =>
                  Number(s.aqi || 0)
                )
              ).toFixed(0)}
            />

            <SummaryCard
              title="Average AQI"
              value={(
                stations.reduce(
                  (sum, station) =>
                    sum + Number(station.aqi || 0),
                  0
                ) / stations.length
              ).toFixed(2)}
            />

          </div>

        )}

      </div>

      {/* ======================================================
          ALL STATIONS
      ====================================================== */}

      <div className="mb-6 rounded-xl bg-white p-6 shadow-sm">

        <div className="mb-5 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">

          <div>

            <h2 className="text-xl font-bold text-gray-800">
              All Live Stations
            </h2>

            <p className="text-sm text-gray-500">
              Showing {stations.length} real-time monitoring stations
            </p>

          </div>

        </div>

        {stations.length === 0 && !liveLoading && (

          <div className="rounded-lg bg-gray-50 p-8 text-center text-gray-500">
            No live station data available.
          </div>

        )}

        {stations.length > 0 && (

          <div className="overflow-x-auto">

            <table className="w-full min-w-[1000px] text-sm">

              <thead>

                <tr className="border-b border-gray-200 text-left">

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    #
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    Station
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    City
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    State
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    AQI
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    PM2.5
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    PM10
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    O₃
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    NO₂
                  </th>

                  <th className="px-4 py-3 font-semibold text-gray-600">
                    Updated
                  </th>

                </tr>

              </thead>

              <tbody>

                {sortedStations.map((station, index) => (

                  <tr
                    key={
                      station.station ||
                      `${station.city}-${index}`
                    }
                    className="border-b border-gray-100 hover:bg-gray-50"
                  >

                    <td className="px-4 py-3 text-gray-500">
                      {index + 1}
                    </td>

                    <td className="max-w-[300px] px-4 py-3 font-medium text-gray-800">
                      {station.station || "Unknown Station"}
                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.city || "N/A"}
                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.state || "N/A"}
                    </td>

                    <td className="px-4 py-3">

                      <span
                        className={`inline-flex rounded-full px-3 py-1 font-bold ${getAQIClass(
                          station.aqi
                        )}`}
                      >
                        {Number(
                          station.aqi || 0
                        ).toFixed(0)}
                      </span>

                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.pm25 ?? "N/A"}
                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.pm10 ?? "N/A"}
                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.o3 ?? "N/A"}
                    </td>

                    <td className="px-4 py-3 text-gray-700">
                      {station.no2 ?? "N/A"}
                    </td>

                    <td className="px-4 py-3 text-gray-500">
                      {station.last_update || "N/A"}
                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        )}

      </div>

      {/* ======================================================
          HPC BENCHMARK BUTTON
      ====================================================== */}

      <div className="mb-6">

        <button
          onClick={runBenchmark}
          disabled={loading}
          className="rounded-lg bg-[#7b1e2b] px-5 py-3 font-semibold text-white hover:bg-[#641823] disabled:opacity-50"
        >
          {loading
            ? "Running Benchmark..."
            : "Run HPC Benchmark"}
        </button>

      </div>

      {/* ======================================================
          HPC ERROR
      ====================================================== */}

      {error && (

        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>

      )}

      {/* ======================================================
          HPC RESULTS
      ====================================================== */}

      {data && (

        <div className="space-y-6">

          {/* WORKLOAD */}

          <div className="rounded-xl bg-white p-6 shadow-sm">

            <h2 className="text-xl font-bold text-gray-800">
              HPC Workload
            </h2>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">

              <div>
                <p className="text-sm text-gray-500">
                  Dataset
                </p>

                <p className="font-semibold">
                  {data.workload?.dataset ?? "N/A"}
                </p>
              </div>

              <div>
                <p className="text-sm text-gray-500">
                  Records
                </p>

                <p className="font-semibold">
                  {data.workload?.records ?? "N/A"}
                </p>
              </div>

              <div>
                <p className="text-sm text-gray-500">
                  Framework
                </p>

                <p className="font-semibold">
                  {data.framework ?? "N/A"}
                </p>
              </div>

            </div>

          </div>

          {/* PROCESSING */}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">

            <ProcessingCard
              title="Sequential"
              result={data.sequential}
            />

            <ProcessingCard
              title="OpenMP"
              result={data.openmp}
            />

            <ProcessingCard
              title="MPI"
              result={data.mpi}
            />

          </div>

          {/* PERFORMANCE */}

          <div className="rounded-xl bg-white p-6 shadow-sm">

            <h2 className="text-xl font-bold text-gray-800">
              Performance Comparison
            </h2>

            <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-4">

              <MetricCard
                title="OpenMP Speedup"
                value={
                  data.comparison?.openmp_speedup != null
                    ? `${Number(
                        data.comparison.openmp_speedup
                      ).toFixed(3)}×`
                    : "N/A"
                }
              />

              <MetricCard
                title="MPI Speedup"
                value={
                  data.comparison?.mpi_speedup != null
                    ? `${Number(
                        data.comparison.mpi_speedup
                      ).toFixed(3)}×`
                    : "N/A"
                }
              />

              <MetricCard
                title="OpenMP Efficiency"
                value={
                  data.comparison
                    ?.openmp_efficiency_percent != null
                    ? `${Number(
                        data.comparison
                          .openmp_efficiency_percent
                      ).toFixed(2)}%`
                    : "N/A"
                }
              />

              <MetricCard
                title="MPI Efficiency"
                value={
                  data.comparison
                    ?.mpi_efficiency_percent != null
                    ? `${Number(
                        data.comparison
                          .mpi_efficiency_percent
                      ).toFixed(2)}%`
                    : "N/A"
                }
              />

            </div>

          </div>

          {/* RESULTS MATCH */}

          <div className="rounded-xl bg-white p-6 shadow-sm">

            <h2 className="text-xl font-bold text-gray-800">
              Result Validation
            </h2>

            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">

              <ValidationCard
                title="OpenMP Results"
                value={
                  data.comparison?.openmp_results_match
                }
              />

              <ValidationCard
                title="MPI Results"
                value={
                  data.comparison?.mpi_results_match
                }
              />

              <ValidationCard
                title="All Results"
                value={
                  data.comparison?.all_results_match
                }
              />

            </div>

          </div>

        </div>

      )}

    </div>
  );
}


// ============================================================
// SUMMARY CARD
// ============================================================

function SummaryCard({ title, value }) {
  return (
    <div className="rounded-lg bg-[#f6f8f7] p-5">

      <p className="text-sm text-gray-500">
        {title}
      </p>

      <p className="mt-2 text-3xl font-bold text-[#7b1e2b]">
        {value}
      </p>

    </div>
  );
}


// ============================================================
// PROCESSING CARD
// ============================================================

function ProcessingCard({ title, result }) {
  return (
    <div className="rounded-xl bg-white p-6 shadow-sm">

      <h2 className="text-xl font-bold text-gray-800">
        {title}
      </h2>

      <div className="mt-5 space-y-3">

        <ResultRow
          label="Processes / Threads"
          value={
            result?.processes ??
            result?.threads ??
            "N/A"
          }
        />

        <ResultRow
          label="Records"
          value={result?.records}
        />

        <ResultRow
          label="Average AQI"
          value={result?.average_aqi}
        />

        <ResultRow
          label="Minimum AQI"
          value={result?.minimum_aqi}
        />

        <ResultRow
          label="Maximum AQI"
          value={result?.maximum_aqi}
        />

        <ResultRow
          label="Execution Time"
          value={
            result?.execution_time_seconds != null
              ? `${result.execution_time_seconds} s`
              : "N/A"
          }
        />

      </div>

    </div>
  );
}


// ============================================================
// RESULT ROW
// ============================================================

function ResultRow({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 pb-2">

      <span className="text-gray-500">
        {label}
      </span>

      <span className="font-semibold text-gray-800">
        {value ?? "N/A"}
      </span>

    </div>
  );
}


// ============================================================
// METRIC CARD
// ============================================================

function MetricCard({ title, value }) {
  return (
    <div className="rounded-lg bg-[#f6f8f7] p-5 text-center">

      <p className="text-sm text-gray-500">
        {title}
      </p>

      <p className="mt-2 text-3xl font-bold text-[#7b1e2b]">
        {value}
      </p>

    </div>
  );
}


// ============================================================
// VALIDATION CARD
// ============================================================

function ValidationCard({ title, value }) {
  const matched = value === true;

  return (
    <div className="rounded-lg bg-[#f6f8f7] p-5 text-center">

      <p className="text-sm text-gray-500">
        {title}
      </p>

      <p
        className={`mt-2 text-2xl font-bold ${
          matched
            ? "text-green-600"
            : "text-red-600"
        }`}
      >
        {value == null
          ? "N/A"
          : matched
          ? "MATCH"
          : "MISMATCH"}
      </p>

    </div>
  );
}

