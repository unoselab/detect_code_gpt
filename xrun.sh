#!/usr/bin/env bash

echo "===== GPU 0: b07489f0 ====="
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-0/python_fun_window_npr_scores.csv
grep b07489f0 output/snapshot_npr/run-x-a11/results/gpu-0/python_fun_window_npr_scores.csv
echo
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-0/python_fun_npr_failures.csv
grep b07489f0 output/snapshot_npr/run-x-a11/results/gpu-0/python_fun_npr_failures.csv
echo

echo "===== GPU 1: 2acee67a ====="
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-1/python_fun_window_npr_scores.csv
grep 2acee67a output/snapshot_npr/run-x-a11/results/gpu-1/python_fun_window_npr_scores.csv
echo
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-1/python_fun_npr_failures.csv
grep 2acee67a output/snapshot_npr/run-x-a11/results/gpu-1/python_fun_npr_failures.csv
echo

echo "===== GPU 2: a00c3b59 ====="
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_window_npr_scores.csv
grep a00c3b59 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_window_npr_scores.csv
echo
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_npr_failures.csv
grep a00c3b59 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_npr_failures.csv
echo

echo "===== GPU 2: ab5df625 ====="
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_window_npr_scores.csv
grep ab5df625 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_window_npr_scores.csv
echo
head -n 1 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_npr_failures.csv
grep ab5df625 output/snapshot_npr/run-x-a11/results/gpu-2/python_fun_npr_failures.csv
echo
