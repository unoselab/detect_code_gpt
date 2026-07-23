python - <<'PY'
import pandas as pd

unique_bodies = pd.read_csv(
    "output/commit_function/run-1a/strict/commit_function_detectcodegpt_unique_bodies.csv"
)

for sha in [
    "3dc5668d3020efd0db870791431326ed9b4280002af4ef7d61ca4dc4d4229f69",
    "b53a8eeefef8476fcf425814a58cc61771df95d39feb2f37f8bd211c0142b11e",
]:
    row = unique_bodies.loc[unique_bodies["function_body_sha256"] == sha]
    if row.empty:
        print(f"=== {sha[:12]} === NOT FOUND in unique_bodies manifest")
        continue
    row = row.iloc[0]
    path = f"output/commit_function/run-1a/strict/{row['function_body_relative_path']}"
    print(f"=== {sha[:12]} ===")
    print(f"token_count={row.get('function_body_split_space_token_count')}  "
          f"windows={row.get('n_128_token_windows')}  "
          f"references={row.get('referencing_function_event_count')}")
    print("-" * 40)
    print(open(path, encoding="utf-8").read())
    print()
PY