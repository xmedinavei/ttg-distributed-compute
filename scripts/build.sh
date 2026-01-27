#!/bin/bash
#
# Build Docker image for TTG worker
#
# Usage:
#   ./build.sh              # Build for local kind
#   ./build.sh --push       # Build and push to ACR (Azure)
#   ./build.sh --acr <name> # Build for specific ACR

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="ttg-worker"
IMAGE_TAG="latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILE="$PROJECT_ROOT/docker/Dockerfile"

# Parse arguments
PUSH=false
ACR_NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --acr)
            ACR_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"

# Build the image
cd "$PROJECT_ROOT"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -f ${DOCKERFILE} .

echo -e "${GREEN}✓ Build complete${NC}"

# If ACR specified, tag and push
if [ -n "$ACR_NAME" ]; then
    FULL_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
    
    echo -e "${YELLOW}Tagging for ACR: ${FULL_IMAGE}${NC}"
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}
    
    if [ "$PUSH" = true ]; then
        echo -e "${YELLOW}Pushing to ACR...${NC}"
        docker push ${FULL_IMAGE}
        echo -e "${GREEN}✓ Pushed to ${FULL_IMAGE}${NC}"
    fi
fi

# Check if kind cluster exists and load image
if command -v kind &> /dev/null; then
    if kind get clusters 2>/dev/null | grep -q "ttg-sandbox"; then
        echo -e "${YELLOW}Loading image into kind cluster...${NC}"
        kind load docker-image ${IMAGE_NAME}:${IMAGE_TAG} --name ttg-sandbox
        echo -e "${GREEN}✓ Image loaded into kind cluster${NC}"
    fi
fi

echo ""
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Next steps:"
echo "  Local (kind):  kubectl apply -f k8s/manifests/parallel-jobs.yaml"
echo "  Azure (AKS):   Update image reference in manifest, then apply"
