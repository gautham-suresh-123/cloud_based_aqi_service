#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>

#define CUDA_CHECK(call)                                      \
do                                                            \
{                                                             \
    cudaError_t error = call;                                 \
    if (error != cudaSuccess)                                 \
    {                                                         \
        fprintf(stderr, "CUDA Error: %s\n",                  \
                cudaGetErrorString(error));                  \
        return 1;                                             \
    }                                                         \
} while (0)


__global__ void calculate_statistics(
    const double *aqi,
    double *sum,
    double *minimum,
    double *maximum,
    int n)
{
    int index = blockIdx.x * blockDim.x + threadIdx.x;

    if (index < n)
    {
        atomicAdd(sum, aqi[index]);

        atomicMin(
            (unsigned long long *)minimum,
            __double_as_longlong(aqi[index])
        );

        atomicMax(
            (unsigned long long *)maximum,
            __double_as_longlong(aqi[index])
        );
    }
}


int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        printf("Usage: %s <csv_file>\n", argv[0]);
        return 1;
    }

    FILE *file = fopen(argv[1], "r");

    if (file == NULL)
    {
        perror("Error opening CSV file");
        return 1;
    }

    char line[4096];

    /* Skip CSV header */
    if (fgets(line, sizeof(line), file) == NULL)
    {
        printf("Empty CSV file\n");
        fclose(file);
        return 1;
    }

    /*
     * First pass: count records
     */
    int records = 0;

    while (fgets(line, sizeof(line), file))
    {
        records++;
    }

    if (records == 0)
    {
        printf("No records found\n");
        fclose(file);
        return 1;
    }

    rewind(file);

    /* Skip header again */
    fgets(line, sizeof(line), file);

    double *h_aqi =
        (double *)malloc(records * sizeof(double));

    if (h_aqi == NULL)
    {
        printf("Host memory allocation failed\n");
        fclose(file);
        return 1;
    }

    /*
     * Read AQI column
     *
     * Cleaned CSV:
     *
     * 0 last_update
     * 1 station
     * 2 city
     * 3 state
     * 4 latitude
     * 5 longitude
     * 6 aqi
     * 7 pm25
     * ...
     */
    int valid_records = 0;

    while (fgets(line, sizeof(line), file))
    {
        char *token;
        char *rest = line;
        int column = 0;
        double aqi = 0.0;

        token = strtok_r(rest, ",", &rest);

        while (token != NULL)
        {
            if (column == 6)
            {
                aqi = atof(token);
                break;
            }

            column++;
            token = strtok_r(NULL, ",", &rest);
        }

        if (aqi >= 0.0 && aqi <= 500.0)
        {
            h_aqi[valid_records] = aqi;
            valid_records++;
        }
    }

    fclose(file);

    /*
     * Allocate GPU memory
     */
    double *d_aqi;
    double *d_sum;
    double *d_minimum;
    double *d_maximum;

    CUDA_CHECK(cudaMalloc(
        (void **)&d_aqi,
        valid_records * sizeof(double)
    ));

    CUDA_CHECK(cudaMalloc(
        (void **)&d_sum,
        sizeof(double)
    ));

    CUDA_CHECK(cudaMalloc(
        (void **)&d_minimum,
        sizeof(double)
    ));

    CUDA_CHECK(cudaMalloc(
        (void **)&d_maximum,
        sizeof(double)
    ));

    /*
     * Copy input data CPU → GPU
     */
    CUDA_CHECK(cudaMemcpy(
        d_aqi,
        h_aqi,
        valid_records * sizeof(double),
        cudaMemcpyHostToDevice
    ));

    double zero = 0.0;
    double minimum = 1e9;
    double maximum = -1e9;

    CUDA_CHECK(cudaMemcpy(
        d_sum,
        &zero,
        sizeof(double),
        cudaMemcpyHostToDevice
    ));

    CUDA_CHECK(cudaMemcpy(
        d_minimum,
        &minimum,
        sizeof(double),
        cudaMemcpyHostToDevice
    ));

    CUDA_CHECK(cudaMemcpy(
        d_maximum,
        &maximum,
        sizeof(double),
        cudaMemcpyHostToDevice
    ));

    /*
     * CUDA configuration
     */
    int threads_per_block = 256;

    int blocks =
        (valid_records + threads_per_block - 1)
        / threads_per_block;

    /*
     * GPU timing
     */
    cudaEvent_t start;
    cudaEvent_t stop;

    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    CUDA_CHECK(cudaEventRecord(start));

    calculate_statistics<<<blocks, threads_per_block>>>(
        d_aqi,
        d_sum,
        d_minimum,
        d_maximum,
        valid_records
    );

    CUDA_CHECK(cudaEventRecord(stop));
    CUDA_CHECK(cudaEventSynchronize(stop));

    float gpu_time = 0.0f;

    CUDA_CHECK(cudaEventElapsedTime(
        &gpu_time,
        start,
        stop
    ));

    /*
     * Copy results GPU → CPU
     */
    double h_sum;
    double h_minimum;
    double h_maximum;

    CUDA_CHECK(cudaMemcpy(
        &h_sum,
        d_sum,
        sizeof(double),
        cudaMemcpyDeviceToHost
    ));

    CUDA_CHECK(cudaMemcpy(
        &h_minimum,
        d_minimum,
        sizeof(double),
        cudaMemcpyDeviceToHost
    ));

    CUDA_CHECK(cudaMemcpy(
        &h_maximum,
        d_maximum,
        sizeof(double),
        cudaMemcpyDeviceToHost
    ));

    double average =
        h_sum / valid_records;

    /*
     * Output
     */
    printf("CUDA_RESULT\n");
    printf("gpu=CUDA\n");
    printf("blocks=%d\n", blocks);
    printf("threads_per_block=%d\n", threads_per_block);
    printf("records=%d\n", valid_records);
    printf("average_aqi=%.2f\n", average);
    printf("minimum_aqi=%.2f\n", h_minimum);
    printf("maximum_aqi=%.2f\n", h_maximum);
    printf("gpu_execution_time_ms=%.6f\n", gpu_time);

    /*
     * Cleanup
     */
    cudaFree(d_aqi);
    cudaFree(d_sum);
    cudaFree(d_minimum);
    cudaFree(d_maximum);

    free(h_aqi);

    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return 0;
}

