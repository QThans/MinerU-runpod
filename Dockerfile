# 使用 PaddleX 官方 CPU 高性能推理镜像
FROM ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/paddlex:paddlex3.3.11-paddlepaddle3.2.0-cpu

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 升级 paddlepaddle 和 paddlex/paddleocr 到最新版本
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade paddlepaddle paddlex paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 ONNX Runtime 和 HPI 依赖
RUN python3 -m pip install onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    paddleocr install_hpi_deps cpu || true

# 设置环境变量
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true

COPY app.py ./

EXPOSE 8000

ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
