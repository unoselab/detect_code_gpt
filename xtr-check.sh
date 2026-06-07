#!/bin/bash
set -euo pipefail

# 1. 작업 디렉토리 및 목적지 경로 정의
cd ~/project-workspace/detect_code_gpt
TARGET_DIR="$HOME/Desktop/tmp02"

# 2. 복사할 목적지 디렉토리가 없으면 자동 생성
mkdir -p "$TARGET_DIR"

echo "========================================================================="
echo " [1/2] Current Log Files Status (Sorted by Timestamp):"
echo "========================================================================="
# 화면에 기존 스타일대로 정렬된 파일 목록 출력
find logs -type f \( \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files_bucket_summary.csv" -o \
  -name "npr_chunks_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "results_cache_main_mixedcode_benchmark_mixedcode_*_50files.pkl" \
\) -printf "%TY-%Tm-%Td %TH:%TM  %p\n" | sort

echo ""
echo "========================================================================="
echo " [2/2] Copying Results to $TARGET_DIR ..."
echo "========================================================================="

# 3. 동일한 조건의 파일들을 find로 수집하여 한 번에 복사 실행
# -exec cp --parents 옵션을 사용하여 logs/ 내부의 하위 구조를 유지하며 안전하게 복사합니다.
find logs -type f \( \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files_bucket_summary.csv" -o \
  -name "npr_chunks_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "results_cache_main_mixedcode_benchmark_mixedcode_*_50files.pkl" \
\) -exec cp --parents -v {} "$TARGET_DIR/" \;

echo "========================================================================="
echo "✅ [Success] All matching logs have been successfully copied."
echo "========================================================================="
