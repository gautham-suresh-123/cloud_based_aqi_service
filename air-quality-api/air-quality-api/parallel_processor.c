#include <stdio.h>
#include <omp.h>

int main() {
    int n = 1000000;
    double sum = 0.0;

    double start = omp_get_wtime();

    #pragma omp parallel for reduction(+:sum)
    for (int i = 0; i < n; i++) {
        sum += i * 0.001;
    }

    double end = omp_get_wtime();

    printf("OpenMP Parallel Processing\n");
    printf("Threads: %d\n", omp_get_max_threads());
    printf("Records processed: %d\n", n);
    printf("Result: %.2f\n", sum);
    printf("Execution time: %.6f seconds\n", end - start);

    return 0;
}
