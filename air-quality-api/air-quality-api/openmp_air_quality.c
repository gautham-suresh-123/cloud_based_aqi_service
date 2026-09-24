#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <omp.h>

#define MAX_LINE 4096

int main(int argc, char *argv[])
{
    if (argc < 2) {
        printf("ERROR: CSV file path required\n");
        return 1;
    }

    const char *filename = argv[1];

    FILE *file = fopen(filename, "r");

    if (file == NULL) {
        printf("ERROR: Cannot open CSV file\n");
        return 1;
    }

    char line[MAX_LINE];

    int records = 0;

    /* Skip header */
    fgets(line, sizeof(line), file);

    /* Count records */
    while (fgets(line, sizeof(line), file)) {
        records++;
    }

    fclose(file);

    if (records == 0) {
        printf("ERROR: No records found\n");
        return 1;
    }

    double *aqi = malloc(records * sizeof(double));

    if (aqi == NULL) {
        printf("ERROR: Memory allocation failed\n");
        return 1;
    }

    file = fopen(filename, "r");

    if (file == NULL) {
        free(aqi);
        return 1;
    }

    /* Skip header */
    fgets(line, sizeof(line), file);

    int index = 0;

    /*
       CSV format:
       last_update,
       station,
       city,
       state,
       latitude,
       longitude,
       aqi,
       pm25,
       pm10,
       no2,
       so2,
       co,
       o3,
       nh3
    */

    while (fgets(line, sizeof(line), file) && index < records)
    {
        char *token;
        int column = 0;

        token = strtok(line, ",");

        while (token != NULL)
        {
            if (column == 6)
            {
                aqi[index] = atof(token);
                index++;
                break;
            }

            token = strtok(NULL, ",");
            column++;
        }
    }

    fclose(file);

    records = index;

    if (records == 0)
    {
        free(aqi);
        printf("ERROR: AQI data not found\n");
        return 1;
    }

    double total_aqi = 0.0;
    double minimum_aqi = 1000000.0;
    double maximum_aqi = 0.0;

    double start = omp_get_wtime();

    /*
       REAL OPENMP PARALLEL PROCESSING
    */

    #pragma omp parallel for reduction(+:total_aqi) reduction(min:minimum_aqi) reduction(max:maximum_aqi)
    for (int i = 0; i < records; i++)
    {
        double value = aqi[i];

        total_aqi += value;

        if (value < minimum_aqi)
            minimum_aqi = value;

        if (value > maximum_aqi)
            maximum_aqi = value;
    }

    double end = omp_get_wtime();

    double average_aqi = total_aqi / records;

    printf("OPENMP_RESULT\n");
    printf("threads=%d\n", omp_get_max_threads());
    printf("records=%d\n", records);
    printf("average_aqi=%.2f\n", average_aqi);
    printf("minimum_aqi=%.2f\n", minimum_aqi);
    printf("maximum_aqi=%.2f\n", maximum_aqi);
    printf("execution_time=%.9f\n", end - start);

    free(aqi);

    return 0;
}

