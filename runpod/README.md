# MinerU RunPod Serverless Deployment

Deploy [MinerU](https://github.com/opendatalab/MinerU) as a serverless endpoint on [RunPod](https://www.runpod.io/).

## Features

- PDF to Markdown/JSON conversion
- Image OCR support (PNG, JPEG, WebP, etc.)
- 109 languages supported for OCR
- Multiple parsing backends (pipeline, vlm, hybrid)
- Formula and table extraction

## Quick Start

### 1. Build and Push Image

```bash
# Set your GitHub credentials
export GITHUB_USERNAME="your-username"
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"  # Create at https://github.com/settings/tokens

# Build and push to GHCR
./build.sh --push --latest
```

### 2. Make Image Public (Recommended)

1. Go to https://github.com/YOUR_USERNAME?tab=packages
2. Click on `mineru-runpod`
3. Package settings → Change visibility → Public

### 3. Deploy on RunPod

#### Option A: Serverless Endpoint (Recommended for Production)

1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Click "New Endpoint"
3. Enter image: `ghcr.io/YOUR_USERNAME/mineru-runpod:latest`
4. Select GPU: RTX 4090 / A10G / A100 (10GB+ VRAM required)
5. Configure scaling (min/max workers)

#### Option B: GPU Pod (For Development/Testing)

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click "Deploy" → "GPU Pod"
3. Enter image: `ghcr.io/YOUR_USERNAME/mineru-runpod:latest`
4. Select GPU and deploy

## API Usage

### Request Format

```json
{
  "input": {
    "file_base64": "base64_encoded_content",  // OR
    "file_url": "https://example.com/doc.pdf",
    "file_name": "document.pdf",              // Optional, for extension detection
    "backend": "hybrid-auto-engine",          // Optional
    "method": "auto",                         // Optional
    "lang": "ch",                             // Optional
    "return_format": "markdown",              // Optional
    "formula_enable": true,                   // Optional
    "table_enable": true,                     // Optional
    "start_page": 0,                          // Optional
    "end_page": 99999                         // Optional
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_base64` | string | - | Base64 encoded file (PDF or image) |
| `file_url` | string | - | URL to download file from |
| `file_name` | string | input.pdf | Filename for extension detection |
| `backend` | string | hybrid-auto-engine | Parsing backend |
| `method` | string | auto | Parsing method (auto/txt/ocr) |
| `lang` | string | ch | Document language for OCR |
| `return_format` | string | markdown | Output format |
| `formula_enable` | bool | true | Enable formula parsing |
| `table_enable` | bool | true | Enable table parsing |
| `start_page` | int | 0 | Starting page (0-based) |
| `end_page` | int | 99999 | Ending page (0-based) |

### Backends

| Backend | Description | VRAM Required |
|---------|-------------|---------------|
| `pipeline` | General purpose, multi-language, no hallucination | 6 GB |
| `vlm-auto-engine` | High accuracy, local GPU | 10 GB |
| `hybrid-auto-engine` | Best accuracy, local GPU | 10 GB |
| `vlm-http-client` | High accuracy, remote server | - |
| `hybrid-http-client` | Best accuracy, remote server | 3-6 GB |

### Languages

| Code | Languages |
|------|-----------|
| `ch` | Chinese, English, Traditional Chinese |
| `en` | English |
| `japan` | Japanese, Chinese, English |
| `korean` | Korean, English |
| `latin` | French, German, Spanish, Italian, etc. |
| `arabic` | Arabic, Persian, Urdu, etc. |
| `cyrillic` | Russian, Ukrainian, Bulgarian, etc. |

### Response Format

```json
{
  "status": "success",
  "backend": "hybrid-auto-engine",
  "method": "auto",
  "lang": "ch",
  "mineru_version": "2.7.0",
  "format": "markdown",
  "content": "# Document Title\n\nExtracted content..."
}
```

## Examples

### Using cURL

```bash
# With PDF URL
curl -X POST "https://api.runpod.ai/v2/{endpoint_id}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "file_url": "https://arxiv.org/pdf/2301.00001.pdf",
      "return_format": "markdown",
      "lang": "en"
    }
  }'

# With Base64 encoded file
curl -X POST "https://api.runpod.ai/v2/{endpoint_id}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"file_base64\": \"$(base64 -i document.pdf)\",
      \"return_format\": \"markdown\"
    }
  }"

# Process an image
curl -X POST "https://api.runpod.ai/v2/{endpoint_id}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"file_base64\": \"$(base64 -i scan.png)\",
      \"file_name\": \"scan.png\",
      \"lang\": \"ch\",
      \"return_format\": \"markdown\"
    }
  }"
```

### Using Python

```python
import runpod
import base64

runpod.api_key = "your_runpod_api_key"
endpoint = runpod.Endpoint("your_endpoint_id")

# With URL
result = endpoint.run_sync({
    "input": {
        "file_url": "https://example.com/document.pdf",
        "return_format": "markdown"
    }
})
print(result["content"])

# With local file
with open("document.pdf", "rb") as f:
    file_base64 = base64.b64encode(f.read()).decode()

result = endpoint.run_sync({
    "input": {
        "file_base64": file_base64,
        "return_format": "markdown"
    }
})
print(result["content"])
```

### Async Processing (for large files)

```bash
# Submit job
JOB_ID=$(curl -s -X POST "https://api.runpod.ai/v2/{endpoint_id}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"input": {"file_url": "https://example.com/large.pdf"}}' \
  | jq -r '.id')

# Check status
curl "https://api.runpod.ai/v2/{endpoint_id}/status/${JOB_ID}" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM | 6 GB | 24 GB |
| System RAM | 16 GB | 32 GB |
| Disk | 20 GB | 50 GB |

### Recommended GPUs

- RTX 4090 (24 GB) - Best price/performance
- A10G (24 GB) - Good for production
- A100 (40/80 GB) - High throughput

## Local Testing

```bash
# Build image locally
./build.sh

# Run with GPU
docker run --gpus all -p 8000:8000 \
  ghcr.io/local/mineru-runpod:1.0.0

# Test with curl
curl -X POST "http://localhost:8000/runsync" \
  -H "Content-Type: application/json" \
  -d '{"input": {"file_url": "https://example.com/test.pdf"}}'
```

## Troubleshooting

### Cold Start Issues

The first request may take longer due to model loading. Consider:
- Setting minimum workers > 0 for always-on capacity
- Using async endpoints for large files

### Out of Memory

- Use `pipeline` backend for lower VRAM usage
- Reduce `end_page` to process fewer pages
- Use a GPU with more VRAM

### Unsupported File Type

Supported formats:
- PDF: `.pdf`
- Images: `.png`, `.jpg`, `.jpeg`, `.jp2`, `.webp`, `.gif`, `.bmp`

## License

This deployment wrapper is provided as-is. MinerU is licensed under [AGPL-3.0](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md).
