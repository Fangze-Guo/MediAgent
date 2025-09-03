# scripts/csv_summary.py
import sys, pandas as pd

if __name__ == "__main__":
    csv_path, delimiter, max_rows = sys.argv[1], sys.argv[2], int(sys.argv[3])
    df = pd.read_csv(csv_path, delimiter=delimiter, nrows=max_rows if max_rows>0 else None)
    desc = df.describe(include="all").to_dict()
    print(desc)
