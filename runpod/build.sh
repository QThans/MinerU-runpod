#!/bin/bash
# MinerU RunPod Build and Deploy Script
#
# This script builds the MinerU Docker image and pushes it to GHCR (GitHub Container Registry)
# for deployment on RunPod.
#
# Usage:
#   ./build.sh                    # Build only
#   ./build.sh --push             # Build and push to GHCR
#   ./build.sh --push --latest    # Build and push with latest tag
#
# Prerequisites:
#   - Docker installed and running
#   - GitHub Personal Access Token with packages:read and packages:write permissions
#   - Set environment variables: GITHUB_USERNAME, GITHUB_TOKEN

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="mineru-runpod"
VERSION="${VERSION:-1.0.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
MinerU RunPod Build Script

Usage: $0 [OPTIONS]

Options:
    --push          Push image to GHCR after building
    --latest        Also tag as 'latest' when pushing
    --no-cache      Build without Docker cache
    --help          Show this help message

Environment Variables:
    GITHUB_USERNAME     Your GitHub username (required for push)
    GITHUB_TOKEN        GitHub Personal Access Token (required for push)
    VERSION             Image version tag (default: 1.0.0)

Examples:
    $0                          # Build image locally
    $0 --push                   # Build and push to GHCR
    $0 --push --latest          # Build and push with latest tag
    VERSION=2.0.0 $0 --push     # Build and push with custom version

EOF
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
}

check_github_credentials() {
    if [ -z "$GITHUB_USERNAME" ]; then
        log_error "GITHUB_USERNAME environment variable is not set."
        echo "Please set it with: export GITHUB_USERNAME=your-username"
        exit 1
    fi

    if [ -z "$GITHUB_TOKEN" ]; then
        log_error "GITHUB_TOKEN environment variable is not set."
        echo "Please create a Personal Access Token at: https://github.com/settings/tokens"
        echo "Required permissions: read:packages, write:packages"
        echo "Then set it with: export GITHUB_TOKEN=ghp_xxxx"
        exit 1
    fi
}

login_ghcr() {
    log_info "Logging in to GitHub Container Registry..."
    echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USERNAME" --password-stdin
    if [ $? -eq 0 ]; then
        log_info "Successfully logged in to GHCR"
    else
        log_error "Failed to login to GHCR"
        exit 1
    fi
}

build_image() {
    local cache_flag=""
    if [ "$NO_CACHE" = true ]; then
        cache_flag="--no-cache"
    fi

    local full_image_name="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

    log_info "Building Docker image: ${full_image_name}"
    log_info "This may take a while (downloading models ~10GB)..."

    docker build \
        --platform linux/amd64 \
        $cache_flag \
        -t "${full_image_name}" \
        -f "${SCRIPT_DIR}/Dockerfile" \
        "${SCRIPT_DIR}"

    if [ $? -eq 0 ]; then
        log_info "Successfully built image: ${full_image_name}"
    else
        log_error "Failed to build image"
        exit 1
    fi

    # Tag as latest if requested
    if [ "$TAG_LATEST" = true ]; then
        local latest_tag="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
        log_info "Tagging as latest: ${latest_tag}"
        docker tag "${full_image_name}" "${latest_tag}"
    fi
}

push_image() {
    local full_image_name="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

    log_info "Pushing image to GHCR: ${full_image_name}"
    docker push "${full_image_name}"

    if [ $? -eq 0 ]; then
        log_info "Successfully pushed: ${full_image_name}"
    else
        log_error "Failed to push image"
        exit 1
    fi

    # Push latest tag if requested
    if [ "$TAG_LATEST" = true ]; then
        local latest_tag="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
        log_info "Pushing latest tag: ${latest_tag}"
        docker push "${latest_tag}"
    fi
}

print_next_steps() {
    local full_image_name="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

    echo ""
    echo "=============================================="
    echo "           Next Steps for RunPod"
    echo "=============================================="
    echo ""
    echo "1. Make the image public (recommended):"
    echo "   - Go to: https://github.com/${GITHUB_USERNAME}?tab=packages"
    echo "   - Click on '${IMAGE_NAME}'"
    echo "   - Go to 'Package settings' -> 'Change visibility' -> 'Public'"
    echo ""
    echo "2. Or configure RunPod with private registry auth:"
    echo "   curl -X POST 'https://rest.runpod.io/v1/containerregistryauth' \\"
    echo "     -H 'Authorization: Bearer \${RUNPOD_API_KEY}' \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"name\": \"ghcr\", \"username\": \"${GITHUB_USERNAME}\", \"password\": \"YOUR_GITHUB_TOKEN\"}'"
    echo ""
    echo "3. Deploy on RunPod:"
    echo "   - GPU Pod: Use image '${full_image_name}'"
    echo "   - Serverless: Create endpoint with image '${full_image_name}'"
    echo ""
    echo "4. Test the endpoint:"
    echo "   curl -X POST 'https://api.runpod.ai/v2/{endpoint_id}/runsync' \\"
    echo "     -H 'Authorization: Bearer \${RUNPOD_API_KEY}' \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"input\": {\"file_url\": \"https://example.com/doc.pdf\", \"return_format\": \"markdown\"}}'"
    echo ""
}

# Parse arguments
PUSH=false
TAG_LATEST=false
NO_CACHE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --latest)
            TAG_LATEST=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
log_info "MinerU RunPod Build Script"
log_info "Version: ${VERSION}"

# Check Docker
check_docker

# Set default GITHUB_USERNAME for local builds if not set
if [ -z "$GITHUB_USERNAME" ]; then
    if [ "$PUSH" = true ]; then
        check_github_credentials
    else
        GITHUB_USERNAME="local"
        log_warn "GITHUB_USERNAME not set, using 'local' for local build"
    fi
fi

# Login to GHCR if pushing
if [ "$PUSH" = true ]; then
    check_github_credentials
    login_ghcr
fi

# Build image
build_image

# Push if requested
if [ "$PUSH" = true ]; then
    push_image
    print_next_steps
else
    log_info "Image built locally. Use --push to push to GHCR."
    echo ""
    echo "Local image: ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
    echo ""
    echo "To test locally:"
    echo "  docker run --gpus all -p 8000:8000 ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
fi

log_info "Done!"
