git switch -c run-1d-gt200-3gpu

# Remove xrun.sh and stage its deletion
git rm xrun.sh

# Keep and stage ylog.txt
git add ylog.txt

# Stage all other intended changes
git add -A -- \
  code-detection/score_commit_function_npr-v0.1.py \
  code-detection/score_commit_function_npr-v0.2.py \
  code-detection/bak/score_commit_function_npr-v0.1.py \
  code-detection/bak/score_commit_function_npr-v0.2.py \
  proc_sh/run-1c-score-commit-func-npr-v0.1.sh \
  proc_sh/run-1c-score-commit-func-npr-v0.2.sh \
  proc_sh/bak/

git add \
  code-detection/analyze_commit_function_input_support-gt200.py \
  code-detection/score_commit_function_npr_full-gt200.py \
  proc_sh/run-1b-analyze-commit-func-input-support-gt200.sh \
  proc_sh/run-1d-score-commit-func-npr-full-gt200.sh \
  workspace-structure-detect-code-gpt-workspace-jul24-r158.txt

# Review before committing
git status
git diff --cached --stat
git diff --cached --summary

git commit -m "Add gt200 three-GPU NPR scoring pipeline"
git push -u origin run-1d-gt200-3gpu

path = "output/snapshot_npr/run-x-a05/snapshot_chunks/control__GispoCoding_qgis-venv-creator__af2c34bcade1__773c29831a026f6d/python_code_unit_manifest.csv"

df = pd.read_csv(path)

primary = df[df["aggregation_role"] == "primary"].copy()

for relpath, group in primary.groupby("relative_path"):
    group = group.sort_values(
        ["start_char_offset", "end_char_offset"],
        kind="mergesort"
    )
    rows = list(group.to_dict("records"))

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            left = rows[i]
            right = rows[j]

            if int(right["start_char_offset"]) >= int(left["end_char_offset"]):
                break

            print("=" * 80)
            print("OVERLAP")
            print("file:", relpath)
            print()
            print(
                "left :",
                left["code_unit_type"],
                left["qualified_name"],
                f'lines={left["start_line"]}-{left["end_line"]}',
                f'chars={left["start_char_offset"]}-{left["end_char_offset"]}',
            )
            print(
                "right:",
                right["code_unit_type"],
                right["qualified_name"],
                f'lines={right["start_line"]}-{right["end_line"]}',
                f'chars={right["start_char_offset"]}-{right["end_char_offset"]}',
            )
PY
