from utils import iter_last_n_lines

for line in iter_last_n_lines(filepath="../arelight.log", n=10):
    print(line)
