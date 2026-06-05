cd code-detection/
CUDA_VISIBLE_DEVICES=0,1,2 python - <<'PY'
import os
print("before:", os.environ.get("CUDA_VISIBLE_DEVICES"))
import main
print("after:", os.environ.get("CUDA_VISIBLE_DEVICES"))
print(main.__file__)
PY