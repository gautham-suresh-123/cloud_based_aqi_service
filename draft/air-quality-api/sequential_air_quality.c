#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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

    if (fgets(line, sizeof(line), file) == NULL)
    {
        printf("Empty CSV file\n");
        fclose(file);
        return 1;
    }

    double total_aqi = 0.0;
    double minimum_aqi = 1e9;
    double maximum_aqi = -1e9;
    long records = 0;

    clock_t start = clock();

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

        if (aqi < 0.0 || aqi > 500.0)
            continue;

        total_aqi += aqi;

        if (aqi < minimum_aqi)
            minimum_aqi = aqi;

        if (aqi > maximum_aqi)
            maximum_aqi = aqi;

        records++;
    }

    clock_t end = clock();

    fclose(file);

    if (records == 0)
    {
        printf("No valid AQI records found\n");
        return 1;
    }

    double average_aqi = total_aqi / records;
    double execution_time =
        (double)(end - start) / CLOCKS_PER_SEC;

    printf("SEQUENTIAL_RESULT\n");
    printf("threads=1\n");
    printf("records=%ld\n", records);
    printf("average_aqi=%.2f\n", average_aqi);
    printf("minimum_aqi=%.2f\n", minimum_aqi);
    printf("maximum_aqi=%.2f\n", maximum_aqi);
    printf("execution_time=%.9f\n", execution_time);

    return 0;
}
