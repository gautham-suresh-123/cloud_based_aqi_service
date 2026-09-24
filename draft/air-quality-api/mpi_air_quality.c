#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <float.h>

#define MAX_RECORDS 10000
#define MAX_LINE 4096

int main(int argc, char *argv[])
{
    int rank, size;

    MPI_Init(&argc, &argv);

    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (argc < 2)
    {
        if (rank == 0)
            printf("Usage: %s <csv_file>\n", argv[0]);

        MPI_Finalize();
        return 1;
    }

    double *all_aqi = NULL;
    int total_records = 0;

    /* Rank 0 reads the CSV */
    if (rank == 0)
    {
        FILE *file = fopen(argv[1], "r");

        if (file == NULL)
        {
            perror("Error opening CSV file");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }

        all_aqi = malloc(MAX_RECORDS * sizeof(double));

        if (all_aqi == NULL)
        {
            printf("Memory allocation failed\n");
            fclose(file);
            MPI_Abort(MPI_COMM_WORLD, 1);
        }

        char line[MAX_LINE];

        /* Skip header */
        if (fgets(line, sizeof(line), file) == NULL)
        {
            printf("Empty CSV file\n");
            fclose(file);
            free(all_aqi);
            MPI_Finalize();
            return 1;
        }

        while (fgets(line, sizeof(line), file))
        {
            char *token;
            char *rest = line;
            int column = 0;
            double aqi = 0.0;
            int found_aqi = 0;

            token = strtok_r(rest, ",", &rest);

            while (token != NULL)
            {
                /*
                 * AQI is column 6 in air_quality_cleaned.csv
                 */
                if (column == 6)
                {
                    aqi = atof(token);
                    found_aqi = 1;
                    break;
                }

                column++;
                token = strtok_r(NULL, ",", &rest);
            }

            if (found_aqi && aqi >= 0.0 && aqi <= 500.0)
            {
                if (total_records < MAX_RECORDS)
                {
                    all_aqi[total_records] = aqi;
                    total_records++;
                }
            }
        }

        fclose(file);
    }

    /* Send record count to all processes */
    MPI_Bcast(
        &total_records,
        1,
        MPI_INT,
        0,
        MPI_COMM_WORLD
    );

    if (total_records == 0)
    {
        if (rank == 0)
            printf("No valid AQI records found\n");

        if (all_aqi != NULL)
            free(all_aqi);

        MPI_Finalize();
        return 1;
    }

    /* Divide records among processes */
    int base = total_records / size;
    int remainder = total_records % size;

    int local_count =
        base + (rank < remainder ? 1 : 0);

    int *counts = NULL;
    int *displacements = NULL;

    if (rank == 0)
    {
        counts = malloc(size * sizeof(int));
        displacements = malloc(size * sizeof(int));

        int offset = 0;

        for (int i = 0; i < size; i++)
        {
            counts[i] =
                base + (i < remainder ? 1 : 0);

            displacements[i] = offset;

            offset += counts[i];
        }
    }

    double *local_aqi =
        malloc(local_count * sizeof(double));

    if (local_aqi == NULL)
    {
        printf("Rank %d: memory allocation failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    MPI_Barrier(MPI_COMM_WORLD);

    double start_time = MPI_Wtime();

    /* Distribute AQI records */
    MPI_Scatterv(
        all_aqi,
        counts,
        displacements,
        MPI_DOUBLE,
        local_aqi,
        local_count,
        MPI_DOUBLE,
        0,
        MPI_COMM_WORLD
    );

    double local_sum = 0.0;
    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;

    /* Local processing */
    for (int i = 0; i < local_count; i++)
    {
        double aqi = local_aqi[i];

        local_sum += aqi;

        if (aqi < local_min)
            local_min = aqi;

        if (aqi > local_max)
            local_max = aqi;
    }

    double global_sum = 0.0;
    double global_min = DBL_MAX;
    double global_max = -DBL_MAX;

    /* Combine results */
    MPI_Reduce(
        &local_sum,
        &global_sum,
        1,
        MPI_DOUBLE,
        MPI_SUM,
        0,
        MPI_COMM_WORLD
    );

    MPI_Reduce(
        &local_min,
        &global_min,
        1,
        MPI_DOUBLE,
        MPI_MIN,
        0,
        MPI_COMM_WORLD
    );

    MPI_Reduce(
        &local_max,
        &global_max,
        1,
        MPI_DOUBLE,
        MPI_MAX,
        0,
        MPI_COMM_WORLD
    );

    MPI_Barrier(MPI_COMM_WORLD);

    double end_time = MPI_Wtime();

    if (rank == 0)
    {
        double execution_time =
            end_time - start_time;

        double average_aqi =
            global_sum / total_records;

        printf("MPI_RESULT\n");
        printf("processes=%d\n", size);
        printf("records=%d\n", total_records);
        printf("average_aqi=%.2f\n", average_aqi);
        printf("minimum_aqi=%.2f\n", global_min);
        printf("maximum_aqi=%.2f\n", global_max);
        printf("execution_time=%.9f\n", execution_time);
    }

    free(local_aqi);

    if (rank == 0)
    {
        free(all_aqi);
        free(counts);
        free(displacements);
    }

    MPI_Finalize();

    return 0;
}
