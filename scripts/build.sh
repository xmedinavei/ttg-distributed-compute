#!/bin/bash
#
# TTG Docker Build Script
#
# Builds the TTG worker Docker image with proper versioning and labels.
#
# Usage:
#   ./build.sh                    # Build with default version (v1.1.0)
#   ./build.sh --version 1.2.0    # Build with specific version
#   ./build.sh --load-kind        # Build and load into kind cluster
#   ./build.sh --push --acr NAME  # Build and push to Azure Container Registry
#
# The script automatically:
#   - Uses git commit hash for build metadata
#   - Adds OCI labels for traceability
#   - Tags with both version and 'latest'
#   - Names the build container for easy identification

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
IMAGE_NAME="ttg-worker"
DEFAULT_VERSION="1.1.0"
KIND_CLUSTER_NAME="ttg-cluster"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILE="$PROJECT_ROOT/docker/Dockerfile"

# Parse arguments
VERSION=""
PUSH=false
ACR_NAME=""
LOAD_KIND=false
NO_CACHE=false

print_usage() {
    echo "TTG Docker Build Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --version, -v VERSION   Set image version (default: $DEFAULT_VERSION)"
    echo "  --load-kind, -k         Load image into kind cluster after build"
    echo "  --push, -p              Push to registry (requires --acr)"
    echo "  --acr NAME              Azure Container Registry name"
    echo "  --no-cache              Build without Docker cache"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Build ttg-worker:v1.1.0"
    echo "  $0 --version 2.0.0           # Build ttg-worker:v2.0.0"
    echo "  $0 --load-kind               # Build and load into kind"
    echo "  $0 --acr myacr --push        # Build and push to ACR"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --push|-p)
            PUSH=true
            shift
            ;;
        --acr)
            ACR_NAME="$2"
            shift 2
            ;;
        --load-kind|-k)
            LOAD_KIND=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Set version
VERSION="${VERSION:-$DEFAULT_VERSION}"
IMAGE_TAG="v${VERSION}"

# Get build metadata
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(cd "$PROJECT_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# ═══════════════════════════════════════════════════════════════════════════
# BUILD
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  TTG Docker Build${NC}"
echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Image:${NC}      ${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  ${CYAN}Version:${NC}    ${VERSION}"
echo -e "  ${CYAN}Build Date:${NC} ${BUILD_DATE}"
echo -e "  ${CYAN}Git Commit:${NC} ${GIT_COMMIT}"
echo -e "  ${CYAN}Git Branch:${NC} ${GIT_BRANCH}"
echo ""

# Build arguments
BUILD_ARGS=(
    --build-arg "VERSION=${VERSION}"
    --build-arg "BUILD_DATE=${BUILD_DATE}"
    --build-arg "GIT_COMMIT=${GIT_COMMIT}"
    -f "$DOCKERFILE"
    -t "${IMAGE_NAME}:${IMAGE_TAG}"
    -t "${IMAGE_NAME}:latest"
)

# Add no-cache if requested
if [ "$NO_CACHE" = true ]; then
    BUILD_ARGS+=(--no-cache)
    echo -e "  ${YELLOW}Building without cache${NC}"
fi

# Build
echo -e "${CYAN}>>> Building Docker image...${NC}"
cd "$PROJECT_ROOT"
docker build "${BUILD_ARGS[@]}" .

echo ""
echo -e "${GREEN}✓ Build complete!${NC}"
echo ""

# Show image details
echo -e "${CYAN}>>> Image details:${NC}"
docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedAt}}"

# Show labels
echo ""
echo -e "${CYAN}>>> Image labels:${NC}"
docker inspect "${IMAGE_NAME}:${IMAGE_TAG}" --format '{{range $k, $v := .Config.Labels}}  {{$k}}: {{$v}}{{"\n"}}{{end}}' | grep -E "^  (ttg\.|org\.opencontainers)" || echo "  (no custom labels found)"

# ═══════════════════════════════════════════════════════════════════════════
# LOAD INTO KIND
# ═══════════════════════════════════════════════════════════════════════════

if [ "$LOAD_KIND" = true ]; then
    echo ""
    echo -e "${CYAN}>>> Loading image into kind cluster...${NC}"
    
    if ! command -v kind &> /dev/null; then
        echo -e "${RED}✗ kind is not installed${NC}"
        exit 1
    fi
    
    if ! kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER_NAME}$"; then
        echo -e "${YELLOW}⚠ Kind cluster '${KIND_CLUSTER_NAME}' not found${NC}"
        echo "  Create it with: kind create cluster --config k8s/local/kind-config.yaml --name ${KIND_CLUSTER_NAME}"
        exit 1
    fi
    
    kind load docker-image "${IMAGE_NAME}:${IMAGE_TAG}" --name "$KIND_CLUSTER_NAME"
    kind load docker-image "${IMAGE_NAME}:latest" --name "$KIND_CLUSTER_NAME"
    
    echo -e "${GREEN}✓ Image loaded into kind cluster '${KIND_CLUSTER_NAME}'${NC}"
    
    # Verify image is in cluster
    echo ""
    echo -e "${CYAN}>>> Verifying image in cluster nodes:${NC}"
    for node in $(docker ps --filter "name=${KIND_CLUSTER_NAME}" --format "{{.Names}}"); do
        echo -n "  $node: "
        if docker exec "$node" crictl images 2>/dev/null | grep -q "${IMAGE_NAME}"; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${YELLOW}loading...${NC}"
        fi
    done
fi

# ═══════════════════════════════════════════════════════════════════════════
# PUSH TO ACR
# ═══════════════════════════════════════════════════════════════════════════

if [ -n "$ACR_NAME" ]; then
    FULL_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}"
    
    echo ""
    echo -e "${CYAN}>>> Tagging for ACR: ${FULL_IMAGE}${NC}"
    
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${FULL_IMAGE}:${IMAGE_TAG}"
    docker tag "${IMAGE_NAME}:latest" "${FULL_IMAGE}:latest"
    
    echo -e "${GREEN}✓ Tagged: ${FULL_IMAGE}:${IMAGE_TAG}${NC}"
    echo -e "${GREEN}✓ Tagged: ${FULL_IMAGE}:latest${NC}"
    
    if [ "$PUSH" = true ]; then
        echo ""
        echo -e "${CYAN}>>> Pushing to ACR...${NC}"
        
        # Check if logged in
        if ! az acr show --name "$ACR_NAME" &>/dev/null; then
            echo -e "${YELLOW}Logging into ACR...${NC}"
            az acr login --name "$ACR_NAME"
        fi
        
        docker push "${FULL_IMAGE}:${IMAGE_TAG}"
        docker push "${FULL_IMAGE}:latest"
        
        echo -e "${GREEN}✓ Pushed to ${FULL_IMAGE}${NC}"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${BLUE}  Build Summary${NC}"
echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} Built:  ${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  ${GREEN}✓${NC} Tagged: ${IMAGE_NAME}:latest"

if [ "$LOAD_KIND" = true ]; then
    echo -e "  ${GREEN}✓${NC} Loaded into kind cluster: ${KIND_CLUSTER_NAME}"
fi

if [ -n "$ACR_NAME" ]; then
    echo -e "  ${GREEN}✓${NC} Tagged for ACR: ${FULL_IMAGE}:${IMAGE_TAG}"
    if [ "$PUSH" = true ]; then
        echo -e "  ${GREEN}✓${NC} Pushed to ACR"
    fi
fi

echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  Deploy to kind:  kubectl apply -f k8s/manifests/parallel-jobs.yaml"
echo "  View logs:       kubectl logs -l app.kubernetes.io/name=ttg-worker -f"
echo "  List resources:  ./scripts/list-resources.sh"
echo ""
