"""
PaddleOCR Document Parser API Service
Provides HTTP endpoint for document parsing using PaddleOCR VL API
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from paddleocr import PaddleOCRVL

app = FastAPI()

# Configuration from environment variables
VL_REC_SERVER_URL = os.getenv("VL_REC_SERVER_URL", "https://api.siliconflow.cn/v1")
VL_REC_API_MODEL_NAME = os.getenv(
    "VL_REC_API_MODEL_NAME", "PaddlePaddle/PaddleOCR-VL-1.5"
)
VL_REC_API_KEY = os.getenv("VL_REC_API_KEY", "")

# Performance configuration
CPU_THREADS = int(os.getenv("CPU_THREADS", "8"))
ENABLE_MKLDNN = os.getenv("ENABLE_MKLDNN", "true").lower() == "true"
ENABLE_HPI = os.getenv("ENABLE_HPI", "true").lower() == "true"
DEVICE = os.getenv("DEVICE", "cpu")  # cpu, gpu, gpu:0, etc.
PRECISION = os.getenv("PRECISION", "fp16")  # fp32, fp16

# Initialize PaddleOCR VL pipeline
pipeline = None


def get_pipeline():
    """Lazy initialization of PaddleOCR VL pipeline"""
    global pipeline
    if pipeline is None:
        pipeline = PaddleOCRVL(
            pipeline_version="v1",
            vl_rec_backend="vllm-server",
            vl_rec_server_url=VL_REC_SERVER_URL,
            vl_rec_api_model_name=VL_REC_API_MODEL_NAME,
            vl_rec_api_key=VL_REC_API_KEY,
            # Performance settings
            device=DEVICE,
            cpu_threads=CPU_THREADS,
            enable_mkldnn=ENABLE_MKLDNN,
            enable_hpi=ENABLE_HPI,
            precision=PRECISION,
        )
    return pipeline


class ParseRequest(BaseModel):
    input: str


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/parse")
def parse_document(request: ParseRequest):
    """
    Parse document using PaddleOCR VL

    Request body (JSON):
        - input: URL or file path of the document/image

    Returns:
        - result: OCR parsing result
        - status: success/error
    """
    try:
        ocr = get_pipeline()
        result = ocr.predict(request.input)

        # Convert result to serializable format
        output = []
        for item in result:
            if hasattr(item, "to_dict"):
                output.append(item.to_dict())
            elif hasattr(item, "__dict__"):
                output.append(item.__dict__)
            else:
                output.append(str(item))

        return {"status": "success", "result": output}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
