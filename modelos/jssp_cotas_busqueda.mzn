% Variante V2: cotas + estrategia de busqueda (se ejecuta SIN -f).
include "globals.mzn";

int: n_jobs;
int: n_machines;
array[1..n_jobs, 1..n_machines] of int: machines;
array[1..n_jobs, 1..n_machines] of int: durations;

% Cotas calculadas antes de resolver (generar_cotas.py):
%   lb = max(trabajo mas largo, maquina mas cargada)
%   ub = mejor makespan de una heuristica de despacho (Giffler-Thompson)
int: lb;
int: ub;

array[1..n_jobs, 1..n_machines] of var 0..ub: s;
var lb..ub: makespan;

% Cada operacion empieza despues de sus predecesoras en el trabajo y deja
% tiempo para terminar las siguientes antes de ub.
constraint forall(j in 1..n_jobs, o in 1..n_machines) (
    s[j, o] >= sum(k in 1..o-1)(durations[j, k]) /\
    s[j, o] + sum(k in o..n_machines)(durations[j, k]) <= ub
);

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

% Estrategia: fijar primero la operacion que puede empezar mas temprano,
% asignandole su inicio mas temprano posible.
solve :: int_search([s[j, o] | j in 1..n_jobs, o in 1..n_machines] ++ [makespan],
                    smallest, indomain_min)
      minimize makespan;

output ["makespan = \(makespan);\n"] ++
       [if o == 1 then "job\(j): " else "" endif ++
        "\(s[j,o]) " ++
        if o == n_machines then "\n" else "" endif
        | j in 1..n_jobs, o in 1..n_machines];
