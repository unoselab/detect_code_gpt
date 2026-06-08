## === Step 1 =======================================
# cd ~/project-workspace/detect_code_gpt
# CUDA_DEVICE=0,1,2 LIMIT=5 N_PERTURBATION=5 CHUNK_SIZE=2 ./runmain_adapter_5.sh
# ===================================================

## === Step 2 =======================================
cd ~/project-workspace/detect_code_gpt
CUDA_DEVICE=0,1,2 ./runmain_adapter_5.sh


