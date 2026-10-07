# Evo 2 runtime image used unchanged on every platform in this study.
# It holds dependencies only. Study code is copied to each instance at run time
# from a committed revision, so code changes do not require a rebuild.

# Arc's own Dockerfile uses this base. Pinned to the linux/amd64 manifest digest.
FROM nvcr.io/nvidia/pytorch:25.04-py3@sha256:36c950490fed05b87814bd831929ec7dbdd8282d9c21a2f6691836fbeb6054e2

# openssh-server is only used on RunPod, where the pod is the container.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd

COPY requirements.txt /opt/evo2ops/requirements.txt
# Other packages (safetensors, huggingface_hub, einops) come from, or are constrained by, the base image.
RUN pip install --no-cache-dir -r /opt/evo2ops/requirements.txt

# Fail the build if pieces Evo 2 needs are missing. Importing evo2 itself needs a GPU driver
# (Triton initialises at import), so that import is tested on the GPU by workload W0.
RUN python -c "import torch, flash_attn, transformer_engine; print('torch', torch.__version__, 'flash_attn', flash_attn.__version__)" \
 && pip show evo2 vtx \
 && pip freeze > /opt/evo2ops/pip-freeze.txt

COPY pod-start.sh /opt/evo2ops/pod-start.sh
RUN chmod +x /opt/evo2ops/pod-start.sh

ENV HF_HUB_DISABLE_TELEMETRY=1 PYTHONUNBUFFERED=1
WORKDIR /work
