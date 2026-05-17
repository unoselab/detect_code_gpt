#!/usr/bin/env python3
import json
import argparse

def load_prompts(path):
    prompts = {}
    with open(path, "r") as f:
        for line_no, line in enumerate(f):
            if line.strip():
                obj = json.loads(line)
                prompts[line_no] = obj["prompt"]
    return prompts

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True, help="First outputs.txt")
    p.add_argument("--b", required=True, help="Second outputs.txt")
    args = p.parse_args()

    a = load_prompts(args.a)
    b = load_prompts(args.b)

    common = sorted(set(a) & set(b))
    matched = []
    mismatched = []
    cnt = 0
    for line_no in common:
        if a[line_no] == b[line_no]:
            cnt = cnt + 1
            if cnt <= 2:
                print(a[line_no])
                print("++++++++"*10)
                print(b[line_no])
            matched.append(line_no)
        else:
            mismatched.append(line_no)

    print(f"A rows:        {len(a)}")
    print(f"B rows:        {len(b)}")
    print(f"Common lines:  {len(common)}")
    print(f"Prompt match:  {len(matched)}")
    print(f"Mismatch:      {len(mismatched)}")

    if mismatched:
        print("\nFirst mismatches:")
        for line_no in mismatched[:10]:
            print(f"  line {line_no}")

if __name__ == "__main__":
    main()