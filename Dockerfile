# PaddleOCR Document Parser Dockerfile
# Based on PaddlePaddle official image with PaddleOCR VL API support

FROM paddlepaddle/paddle:3.3.0

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libgl1 \
        libglib2.0-0 \
        curl \
        wget && \
    fc-cache -fv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install PaddleOCR and Flask
RUN pip install --no-cache-dir paddleocr flask

# Set working directory
WORKDIR /app

# Copy application files
COPY app.py /app/app.py

# Environment variables
ENV PYTHONUNBUFFERED=1
# Enable MKL-DNN for CPU optimization
ENV FLAGS_use_mkldnn=1

# Expose port for the service
EXPOSE 8000

# Default command - can be overridden
CMD ["python3", "/app/app.py"]
