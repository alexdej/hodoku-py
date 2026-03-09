import timeit
from hodoku.solver.solver import SudokuSolver

puzzles = [
    ("easy", "530070000600195000098000060800060003400803001700020006060000280000419005000080079"),
    ("expert", "009000005001002000050403207300060000002500000070000400000004090000030006600007100"),
    # grab a few medium, hard, extreme from your test corpus
]

def solve(p):
  solver = SudokuSolver()
  solver.solve(p)

N = 100
for diff, p in puzzles:
    ms = timeit.timeit(lambda: solve(p), number=N) * 1000
    avg = ms / N
    print(f"{diff}:")
    print(f"{N} iterations in {ms:.4f} ms")
    print(f"{avg:.4f} ms per solve")


