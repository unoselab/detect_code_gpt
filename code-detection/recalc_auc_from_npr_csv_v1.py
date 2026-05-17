#!/usr/bin/env python3
import argparse
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--n", type=int, default=530)
    parser.add_argument("--mode", choices=["first", "random"], default="first")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)

    if len(df) < args.n:
        raise ValueError(f"CSV has only {len(df)} rows, cannot sample n={args.n}")

    if args.mode == "first":
        sub = df.head(args.n).copy()
    else:
        sub = df.sample(n=args.n, random_state=args.seed).sort_index().copy()

    y_true = np.concatenate([
        np.zeros(len(sub)),  # HWC
        np.ones(len(sub)),   # MGC
    ])

    y_score = np.concatenate([
        sub["hwc_npr"].to_numpy(),
        sub["mgc_npr"].to_numpy(),
    ])

    auc = roc_auc_score(y_true, y_score)

    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    j = tpr - fpr
    best_idx = int(np.argmax(j))

    print("=" * 72)
    print(f"Input CSV: {args.csv}")
    print(f"Mode:      {args.mode}")
    print(f"n pairs:   {len(sub)}")
    print("=" * 72)
    print(f"DetectCodeGPT AUROC: {auc:.10f}")
    print()
    print("NPR summary:")
    print(f"  HWC mean={sub['hwc_npr'].mean():.4f}, median={sub['hwc_npr'].median():.4f}, std={sub['hwc_npr'].std():.4f}")
    print(f"  MGC mean={sub['mgc_npr'].mean():.4f}, median={sub['mgc_npr'].median():.4f}, std={sub['mgc_npr'].std():.4f}")
    print()
    print("Optimal threshold by Youden's J:")
    print(f"  threshold={thresholds[best_idx]:.4f}")
    print(f"  TPR={tpr[best_idx]:.4f}, FPR={fpr[best_idx]:.4f}, J={j[best_idx]:.4f}")
    print("=" * 72)

if __name__ == "__main__":
    main()
