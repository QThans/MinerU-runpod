# MinerU RunPod Serverless Dockerfile
# Based on official MinerU docker/global/Dockerfile

# Use the official vllm image for GPU with Ampere, Ada Lovelace, Hopper architecture (8.0 <= Compute Capability <= 9.0)
# Compute Capability version query: https://developer.nvidia.com/cuda-gpus
# Only supports x86_64 architecture
FROM vllm/vllm-openai:v0.10.1.1

# Use this for Volta, Turing, Blackwell architecture (7.0 < Compute Capability < 8.0 or >= 10.0)
# Supports x86_64 and ARM(AArch64) architecture
# FROM vllm/vllm-openai:v0.11.0

# Install system dependencies
# - libgl1: OpenCV support
# - fonts-noto-*: Chinese/CJK character support
# - curl: For downloading files from URLs
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libgl1 \
        curl && \
    fc-cache -fv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install MinerU and RunPod SDK
RUN python3 -m pip install -U 'mineru[core]>=2.7.0' runpod --break-system-packages && \
    python3 -m pip cache purge

# Download models and update the configuration file
# This may take a while as models are ~10GB
RUN /bin/bash -c "mineru-models-download -s huggingface -m all"

# Set working directory
WORKDIR /app

# Copy handler
COPY handler.py /app/handler.py

# Environment variables
ENV MINERU_MODEL_SOURCE=local
ENV PYTHONUNBUFFERED=1

# RunPod serverless entry point
CMD ["python3", "/app/handler.py"]
