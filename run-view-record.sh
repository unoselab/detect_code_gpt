# Show the annotated form of any record by id
view_record() {
    local id="${1:-0}"
    local path="${PROJECT_ROOT:-$HOME/project-workspace/detect_code_gpt}/output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs_530_benchmark_level1.jsonl"
    python -c "
import json, sys
with open('$path') as f:
    for line in f:
        r = json.loads(line)
        if r['id'] == $id:
            print(r['mixed_code_annotated'])
            break
"
}

view_record $1

python code-detection/view_benchmark_record.py --record_id $1 --verbose
