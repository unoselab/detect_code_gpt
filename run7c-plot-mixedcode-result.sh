#!/usr/bin/env bash
set -euo pipefail

echo "==================================================="
echo "Mixed-code result plotting"
echo "==================================================="
echo "Current directory before cd:"
pwd
echo ""

echo "[STEP 1] Move to analysis_results"
cd analysis_results
echo "Current directory:"
pwd
echo ""

# echo "==================================================="
# echo "[LIST ONLY] Discover mixed-code result files"
# echo "==================================================="
# echo "[RUN] python plot_mixedcode_results.py \\"
# echo "        --logs_dir ../logs \\"
# echo "        --out_dir mixedcode \\"
# echo "        --list_only"
# echo ""

# python plot_mixedcode_results.py \
#   --logs_dir ../logs \
#   --out_dir mixedcode \
#   --list_only

echo ""
echo "==================================================="
echo "[FULL ARTIFACT GENERATION] Create CSVs, tables, and figures"
echo "==================================================="
echo "[RUN] python plot_mixedcode_results.py \\"
echo "        --logs_dir ../logs \\"
echo "        --out_dir mixedcode"
echo ""

python plot_mixedcode_results.py \
  --logs_dir ../logs \
  --out_dir mixedcode

echo ""
echo "==================================================="
echo "Done. Expected outputs are under:"
echo "  analysis_results/mixedcode"
echo "==================================================="