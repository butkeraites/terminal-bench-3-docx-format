A Costas array of order N is a permutation f of {1, ..., N} such that all the
displacement vectors between pairs of its points are distinct: for every pair of
distinct index pairs (i, j) and (k, l) with i < j and k < l, if j - i == l - k
then f(j) - f(i) != f(l) - f(k).

Equivalently: for every shift h in {1, ..., N-1}, the differences
f(i+h) - f(i) for i = 1, ..., N-h are pairwise distinct.

Write every Costas array of order 19 to `/app/costas19.txt`, one per line, as
the 19 values f(1) ... f(19) separated by single spaces. Order of lines does not
matter, but no array may appear twice and none may be missing.

You have 4 CPUs. You have network access.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
