#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/resource.h>
int main(void) {
    struct rlimit limit;
    if (getrlimit(RLIMIT_CORE, &limit) != 0) return 2;
    printf("%ld %ld %llu %llu\n", (long)getpid(), (long)getuid(),
           (unsigned long long)limit.rlim_cur,
           (unsigned long long)limit.rlim_max);
    fflush(stdout);
    char gate;
    if (read(STDIN_FILENO, &gate, 1) != 1 || gate != 'x') return 3;
    raise(SIGSEGV);
    return 4;
}
