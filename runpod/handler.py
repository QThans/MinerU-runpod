"""
MinerU RunPod Serverless Handler

This handler processes PDF and image files using MinerU and returns
the extracted content in various formats (markdown, JSON, content_list).

Supported input formats:
- PDF files
- Images: png, jpeg, jp2, webp, gif, bmp, jpg

Input parameters:
- file_base64: Base64 encoded file content (PDF or image)
- file_url: URL to download the file from (alternative to file_base64)
- backend: Parsing backend (default: hybrid-auto-engine)
  - pipeline: More general, supports multiple languages
  - vlm-auto-engine: High accuracy via local computing power
  - hybrid-auto-engine: Next-generation high accuracy solution
- method: Parsing method (default: auto)
  - auto: Automatically determine based on file type
  - txt: Use text extraction method
  - ocr: Use OCR method for image-based PDFs
- lang: Document language for OCR (default: ch)
- return_format: Output format (default: markdown)
  - markdown: Return markdown content
  - json: Return middle JSON
  - content_list: Return content list JSON
- formula_enable: Enable formula parsing (default: true)
- table_enable: Enable table parsing (default: true)
- start_page: Starting page for PDF parsing (default: 0)
- end_page: Ending page for PDF parsing (default: None, parse all)
"""

import runpod
import os
import sys
import base64
import tempfile
import shutil
import asyncio
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
from loguru import logger

log_level = os.getenv("MINERU_LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stderr, level=log_level)

# Set environment variables before importing MinerU
os.environ["MINERU_MODEL_SOURCE"] = "local"

# Import MinerU modules
from mineru.cli.common import aio_do_parse, read_fn, pdf_suffixes, image_suffixes
from mineru.version import __version__

# Supported file extensions
SUPPORTED_EXTENSIONS = pdf_suffixes + image_suffixes


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    return Path(filename).suffix.lower().lstrip(".")


def validate_input(job_input: Dict[str, Any]) -> tuple[bool, str]:
    """Validate input parameters."""
    # Check for file input
    if not job_input.get("file_base64") and not job_input.get("file_url"):
        return False, "Missing required parameter: file_base64 or file_url"

    # Validate backend
    valid_backends = [
        "pipeline",
        "vlm-auto-engine",
        "vlm-http-client",
        "hybrid-auto-engine",
        "hybrid-http-client"
    ]
    backend = job_input.get("backend", "hybrid-auto-engine")
    if backend not in valid_backends:
        return False, f"Invalid backend: {backend}. Valid options: {valid_backends}"

    # Validate method
    valid_methods = ["auto", "txt", "ocr"]
    method = job_input.get("method", "auto")
    if method not in valid_methods:
        return False, f"Invalid method: {method}. Valid options: {valid_methods}"

    # Validate return_format
    valid_formats = ["markdown", "json", "content_list"]
    return_format = job_input.get("return_format", "markdown")
    if return_format not in valid_formats:
        return False, f"Invalid return_format: {return_format}. Valid options: {valid_formats}"

    return True, ""


def download_file(url: str, dest_path: str, timeout: int = 300) -> None:
    """Download file from URL."""
    logger.info(f"Downloading file from: {url}")

    # Create request with headers
    headers = {
        "User-Agent": "MinerU-RunPod/1.0"
    }
    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
        logger.info(f"File downloaded successfully: {dest_path}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to download file: {e}")


def get_result_dir(output_dir: str, pdf_name: str, backend: str, parse_method: str) -> str:
    """Get the result directory based on backend type."""
    if backend.startswith("hybrid"):
        return os.path.join(output_dir, pdf_name, f"hybrid_{parse_method}")
    elif backend.startswith("vlm"):
        return os.path.join(output_dir, pdf_name, "vlm")
    else:  # pipeline
        return os.path.join(output_dir, pdf_name, parse_method)


def read_result_file(result_dir: str, pdf_name: str, suffix: str) -> Optional[str]:
    """Read result file content."""
    file_path = os.path.join(result_dir, f"{pdf_name}{suffix}")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return None


async def process_file(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single file with MinerU."""

    # Extract parameters
    file_base64 = job_input.get("file_base64")
    file_url = job_input.get("file_url")
    file_name = job_input.get("file_name", "input.pdf")
    backend = job_input.get("backend", "hybrid-auto-engine")
    parse_method = job_input.get("method", "auto")
    lang = job_input.get("lang", "ch")
    return_format = job_input.get("return_format", "markdown")
    formula_enable = job_input.get("formula_enable", True)
    table_enable = job_input.get("table_enable", True)
    start_page = job_input.get("start_page", 0)
    end_page = job_input.get("end_page", 99999)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="mineru_")
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Determine file extension
        if file_url:
            # Try to get extension from URL
            url_path = urllib.request.urlparse(file_url).path
            ext = get_file_extension(url_path) or "pdf"
        else:
            ext = get_file_extension(file_name) or "pdf"

        # Validate extension
        if ext not in SUPPORTED_EXTENSIONS:
            return {
                "error": f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}"
            }

        # Save input file
        input_filename = f"input.{ext}"
        input_path = os.path.join(temp_dir, input_filename)

        if file_base64:
            logger.info("Decoding base64 file content")
            with open(input_path, "wb") as f:
                f.write(base64.b64decode(file_base64))
        else:
            download_file(file_url, input_path)

        # Read file using MinerU's read_fn (handles both PDF and images)
        logger.info(f"Reading file: {input_path}")
        pdf_bytes = read_fn(input_path)
        pdf_name = "input"

        # Determine what to dump based on return_format
        dump_md = return_format == "markdown"
        dump_middle_json = return_format == "json"
        dump_content_list = return_format == "content_list"

        # Process with MinerU
        logger.info(f"Processing with backend: {backend}, method: {parse_method}")
        await aio_do_parse(
            output_dir=output_dir,
            pdf_file_names=[pdf_name],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=[lang],
            backend=backend,
            parse_method=parse_method,
            formula_enable=formula_enable,
            table_enable=table_enable,
            f_dump_md=dump_md,
            f_dump_middle_json=dump_middle_json,
            f_dump_content_list=dump_content_list,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_orig_pdf=False,
            f_dump_model_output=False,
            start_page_id=start_page,
            end_page_id=end_page,
        )

        # Get result directory
        result_dir = get_result_dir(output_dir, pdf_name, backend, parse_method)

        # Read result based on format
        result = {
            "status": "success",
            "backend": backend,
            "method": parse_method,
            "lang": lang,
            "mineru_version": __version__,
        }

        if return_format == "markdown":
            content = read_result_file(result_dir, pdf_name, ".md")
            if content:
                result["content"] = content
                result["format"] = "markdown"
            else:
                result["status"] = "error"
                result["error"] = "Failed to generate markdown output"

        elif return_format == "json":
            content = read_result_file(result_dir, pdf_name, "_middle.json")
            if content:
                result["content"] = content
                result["format"] = "json"
            else:
                result["status"] = "error"
                result["error"] = "Failed to generate JSON output"

        elif return_format == "content_list":
            content = read_result_file(result_dir, pdf_name, "_content_list.json")
            if content:
                result["content"] = content
                result["format"] = "content_list"
            else:
                result["status"] = "error"
                result["error"] = "Failed to generate content list output"

        logger.info(f"Processing completed successfully")
        return result

    except Exception as e:
        logger.exception(f"Error processing file: {e}")
        return {
            "status": "error",
            "error": str(e),
            "backend": backend,
            "mineru_version": __version__,
        }
    finally:
        # Cleanup temporary directory
        logger.info(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod Serverless Handler for MinerU.

    This is the main entry point for RunPod serverless requests.
    """
    job_input = job.get("input", {})

    logger.info(f"Received job: {job.get('id', 'unknown')}")
    logger.debug(f"Input parameters: {list(job_input.keys())}")

    # Validate input
    is_valid, error_msg = validate_input(job_input)
    if not is_valid:
        logger.error(f"Input validation failed: {error_msg}")
        return {"status": "error", "error": error_msg}

    # Run async processing
    try:
        result = asyncio.get_event_loop().run_until_complete(process_file(job_input))
    except RuntimeError:
        # No event loop, create new one
        result = asyncio.run(process_file(job_input))

    return result


# Health check endpoint for RunPod
def health_check() -> bool:
    """Check if the service is healthy."""
    try:
        # Verify MinerU is importable and models are available
        from mineru.cli.common import read_fn
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


if __name__ == "__main__":
    logger.info(f"Starting MinerU RunPod Serverless Handler")
    logger.info(f"MinerU version: {__version__}")
    logger.info(f"Supported file types: {SUPPORTED_EXTENSIONS}")

    # Start RunPod serverless
    runpod.serverless.start({
        "handler": handler,
    })
