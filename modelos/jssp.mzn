include "globals.mzn";

int: n_jobs;
int: n_machines;
array[1..n_jobs, 1..n_machines] of int: machines;
array[1..n_jobs, 1..n_machines] of int: durations;

int: horizon = sum(durations);

array[1..n_jobs, 1..n_machines] of var 0..horizon: s;
var 0..horizon: makespan;

constraint forall(j in 1..n_jobs, o in 1..n_machines-1) (
    s[j, o] + durations[j, o] <= s[j, o+1]
);

constraint forall(m in 0..n_machines-1) (
    let {
        array[1..n_jobs] of var int: ms = [s[j, o] | j in 1..n_jobs, o in 1..n_machines where machines[j, o] == m];
        array[1..n_jobs] of int: md = [durations[j, o] | j in 1..n_jobs, o in 1..n_machines where machines[j, o] == m];
    } in
    disjunctive(ms, md)
);

constraint forall(j in 1..n_jobs) (
    s[j, n_machines] + durations[j, n_machines] <= makespan
);

solve minimize makespan;

output ["makespan = \(makespan);\n"] ++
       [if o == 1 then "job\(j): " else "" endif ++
        "\(s[j,o]) " ++
        if o == n_machines then "\n" else "" endif
        | j in 1..n_jobs, o in 1..n_machines];
