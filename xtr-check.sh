cd ~/project-workspace/detect_code_gpt/analysis_results

python - <<'PY'
from pathlib import Path

p = Path("make_paper_artifacts.py")
s = p.read_text()

old = '''    # colorblind-friendly palette
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]
'''

new = '''    # group/model palette
    palette = ["#845ec2", "#d65db1", "#ff6f91", "#ff9671", "#ffc75f"]
'''

if old not in s:
    raise SystemExit("Could not find the existing palette block.")

p.write_text(s.replace(old, new, 1))
print("Updated figure palette in", p)
PY