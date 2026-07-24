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

