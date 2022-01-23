#include <stdlib.h>

int *generate_random_array(int size) {
    int *array = malloc(sizeof(int) * size * size);
    srand(0);
    for (int i=0; i<size; i++) {
        array[i] = rand();
    }
    return array;
}

int *matmul(int N) {
    int *mat_a = generate_random_array(N);
    int *mat_b = generate_random_array(N);
    int *mat_c = calloc(N * N, sizeof(int));

    for (int i=0; i<N; i++) {
        for (int j=0; j<N; j++) {
            for (int k=0; k<N; k++) {
                mat_c[i*N + j] += mat_a[i*N + k] * mat_b[k*N + j];
            }
        }
    }

    free(mat_a);
    free(mat_b);

    return mat_c;
}

void free_mem(char *ptr) {
    free(ptr);
}