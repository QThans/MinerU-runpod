"""
PaddleOCR Document Parser API Service
Provides HTTP endpoint for document parsing using PaddleOCR VL API
"""

import os
import asyncio
import logging
import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory

import aiofiles
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from paddleocr import PaddleOCRVL

# 配置日志
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PaddleOCR VL API",
    description="API for document parsing using PaddleOCR-VL",
    version="1.0.0",
)

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
DEVICE = os.getenv("DEVICE", "cpu")
PRECISION = os.getenv("PRECISION", "fp16")
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "30"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Initialize PaddleOCR VL pipeline
_pipeline = None


def get_pipeline():
    """Lazy initialization of PaddleOCR VL pipeline"""
    global _pipeline
    if _pipeline is None:
        logger.info(
            f"Initializing PaddleOCR-VL pipeline, vl_rec_server_url={VL_REC_SERVER_URL}"
        )
        _pipeline = PaddleOCRVL(
            layout_detection_model_name="PP-DocLayoutV2",
            vl_rec_backend="vllm-server",
            vl_rec_server_url=VL_REC_SERVER_URL,
            vl_rec_api_model_name=VL_REC_API_MODEL_NAME,
            vl_rec_api_key=VL_REC_API_KEY,
            device=DEVICE,
            cpu_threads=CPU_THREADS,
            enable_mkldnn=ENABLE_MKLDNN,
            enable_hpi=ENABLE_HPI,
            precision=PRECISION,
        )
        logger.info("PaddleOCR-VL pipeline initialized")
    return _pipeline


def _extract_markdown_from_result_sync(pipeline, result) -> tuple[str, int]:
    """Extract markdown content and page count from PaddleOCR-VL result"""
    markdown_list = []
    pages = 0

    try:
        for res in result:
            pages += 1
            md_info = res.markdown
            if md_info:
                markdown_list.append(md_info)
    except Exception as e:
        logger.error(f"Error iterating result: {str(e)}")
        return "", 0

    if not markdown_list:
        return "", 0

    try:
        markdown_texts = pipeline.concatenate_markdown_pages(markdown_list)
        return markdown_texts, pages
    except Exception as e:
        logger.warning(
            f"concatenate_markdown_pages failed: {str(e)}, trying manual merge"
        )
        try:
            text_parts = []
            for md_info in markdown_list:
                if isinstance(md_info, dict):
                    text = (
                        md_info.get("markdown_texts")
                        or md_info.get("markdown_text")
                        or ""
                    )
                    if text:
                        text_parts.append(text)
                elif isinstance(md_info, str):
                    text_parts.append(md_info)
            return "\n\n".join(filter(None, text_parts)), pages
        except Exception as e2:
            logger.error(f"Manual markdown merge failed: {str(e2)}")
            return "", 0


async def _extract_markdown_from_result(pipeline, result) -> tuple[str, int]:
    """Async version: extract markdown from result"""
    return await asyncio.to_thread(_extract_markdown_from_result_sync, pipeline, result)


def _convert_result_sync(result):
    """Convert result to serializable format"""
    output = []
    for item in result:
        if hasattr(item, "to_dict"):
            output.append(item.to_dict())
        elif hasattr(item, "__dict__"):
            output.append(
                {k: v for k, v in item.__dict__.items() if not str(k).startswith("_")}
            )
        else:
            output.append(str(item))
    return output


async def _write_upload_file(
    upload_file: UploadFile, dest_path: Path, max_size_bytes: int
) -> int:
    """Write UploadFile to destination path with size check"""
    chunk_size = 1024 * 1024  # 1MB
    total_written = 0
    async with aiofiles.open(dest_path, "wb") as buffer:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            total_written += len(chunk)
            if total_written > max_size_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large, max size is {MAX_FILE_SIZE_MB}MB",
                )
            await buffer.write(chunk)
    return total_written


class ParseRequest(BaseModel):
    input: str


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "message": "PaddleOCR VL API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "parse_url": "/parse",
            "parse_file": "/parse/file",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/parse")
async def parse_document(request: ParseRequest):
    """
    Parse document using PaddleOCR VL (URL input)

    Request body (JSON):
        - input: URL of the document/image

    Returns:
        - result: OCR parsing result
        - markdown: Extracted markdown content
        - pages: Number of pages
        - status: success/error
    """
    try:
        logger.info(f"Processing URL: {request.input}")
        pipeline = get_pipeline()

        result = await asyncio.to_thread(
            pipeline.predict, input=request.input, use_layout_detection=False
        )

        markdown, pages = await _extract_markdown_from_result(pipeline, result)
        output = await asyncio.to_thread(_convert_result_sync, result)

        logger.info(f"URL processing complete, pages={pages}")
        return {
            "status": "success",
            "result": output,
            "markdown": markdown,
            "pages": pages,
        }

    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/file")
async def parse_file(file: UploadFile = File(...)):
    """
    Parse uploaded file using PaddleOCR VL

    Args:
        file: Uploaded file (PDF, JPG, PNG, BMP)

    Returns:
        - result: OCR parsing result
        - markdown: Extracted markdown content
        - pages: Number of pages
        - status: success/error
    """
    try:
        logger.info(f"Processing file: {file.filename}")

        allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".bmp"}
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty")

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported: {', '.join(allowed_extensions)}",
            )

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / file.filename
            file_size = await _write_upload_file(file, temp_path, MAX_FILE_SIZE_BYTES)

            if file_size == 0:
                raise HTTPException(status_code=400, detail="File is empty")

            mime_type, _ = mimetypes.guess_type(file.filename)
            logger.info(
                f"File saved: path={temp_path}, size={file_size} bytes, mime={mime_type}"
            )

            pipeline = get_pipeline()
            result = await asyncio.to_thread(
                pipeline.predict, input=str(temp_path), use_layout_detection=False
            )

            markdown, pages = await _extract_markdown_from_result(pipeline, result)
            output = await asyncio.to_thread(_convert_result_sync, result)

            logger.info(f"File processing complete, pages={pages}")
            return {
                "status": "success",
                "result": output,
                "markdown": markdown,
                "pages": pages,
                "filename": file.filename,
                "file_size": file_size,
            }

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        logger.error(f"Error processing file: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
