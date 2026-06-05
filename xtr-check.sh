# quick check: are the regenerated line7001-7114 pairs now non-empty MGC?
cd ~/project-workspace/ai_detector
python - <<'PY'
import pandas as pd, sys
sys.path.insert(0, "src")
from code_generation import find_validsyntax_mgc as v
csv = "src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-7b/validsyntax_4500_complexity/codesearchnet_starcoder2-7b_python_merged_4500.csv"
df = pd.read_csv(csv)
new = df[df['idx'].str.extract(r'line(\d+)')[0].astype(int) >= 7001]
bad = 0
for code in new[new['label']=='lm']['code']:
    ok,_ = v.code_has_required_structure(str(code))
    bad += (not ok)
print(f"new lm pairs: {len(new)//2}, empty/docstring-only MGC among them: {bad}")
PY