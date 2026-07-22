# python - <<'PY'
# import pandas as pd
# manifest = pd.read_csv(
#     "../ai_code_complexity_study_python/ai-code-complexity-study/repo_python/run-py-5a-py312/strict/commit_function_detection_manifest.csv"
# )
# treatment = manifest.loc[manifest["dataset_source"] == "treatment"]
# # getsentry/tux처럼 이전에 문제가 많았던 repo를 의도적으로 포함
# sample = pd.concat([
#     treatment.loc[treatment["repo_name"] == "getsentry/sentry"].sample(n=200, random_state=1),
#     treatment.loc[treatment["repo_name"] == "allthingslinux/tux"].sample(n=200, random_state=1),
#     treatment.sample(n=200, random_state=1),
# ])["function_event_id"].drop_duplicates()
# sample.to_csv("event_ids_treatment_stress.csv", index=False)
# print(len(sample), "events selected")
# PY

# PYTHON_BIN=/home/user1-system12/miniconda3/envs/agcparse312/bin/python \
# EVENT_ID_FILE=event_ids_treatment_stress.csv \
# OUTPUT_DIR=output/commit_function/run-1a/smoke_treatment OVERWRITE_OUTPUT=1 \
#   bash proc_sh/run-1a-prepare-input-commit-func.sh


mkdir -p output/commit_function/run-1a/selections

/home/user1-system12/miniconda3/envs/agcparse312/bin/python - <<'PY'
import pandas as pd

manifest_path = (
    "../ai_code_complexity_study_python/ai-code-complexity-study/"
    "repo_python/run-py-5a-py312/strict/"
    "commit_function_detection_manifest.csv"
)
output_path = (
    "output/commit_function/run-1a/selections/"
    "balanced-treatment-control-1000-v1.csv"
)

df = pd.read_csv(manifest_path, dtype=str, low_memory=False)

selected = []
for source in ["treatment", "control"]:
    group = df[df["dataset_source"].eq(source)]
    if len(group) < 500:
        raise SystemExit(f"Not enough {source} events: {len(group)}")
    selected.append(group.sample(n=500, random_state=20260722))

out = pd.concat(selected, ignore_index=True)
out[["function_event_id"]].to_csv(output_path, index=False)

print(out["dataset_source"].value_counts().to_string())
print(f"Saved: {output_path}")
PY

PYTHON_BIN=/home/user1-system12/miniconda3/envs/agcparse312/bin/python \
EVENT_ID_FILE=output/commit_function/run-1a/selections/balanced-treatment-control-1000-v1.csv \
OUTPUT_DIR=output/commit_function/run-1a/smoke1000-balanced-v1 \
OVERWRITE_OUTPUT=1 \
bash proc_sh/run-1a-prepare-input-commit-func.sh

