#!/bin/bash
#
# TTG Virtual Environment Setup Script
# Creates and configures a Python virtual environment for the project
#
# Usage:
#   chmod +x scripts/setup-venv.sh
#   ./scripts/setup-venv.sh
#
# After running, activate the environment:
#   source .venv/bin/activate
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_CMD="python3"

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Main Script
print_header "TTG Python Virtual Environment Setup"

# Check Python version
print_step "Checking Python version..."
if ! command -v $PYTHON_CMD &> /dev/null; then
    print_error "Python 3 is not installed!"
    echo "Please install Python 3.8+ first."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo "  Found: Python $PYTHON_VERSION"

# Check if venv module is available
if ! $PYTHON_CMD -c "import venv" &> /dev/null; then
    print_error "Python venv module not found!"
    echo "Install it with: sudo apt-get install python3-venv"
    exit 1
fi
print_success "Python venv module available"

# Check if virtual environment already exists
if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists at $VENV_DIR"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    else
        print_step "Keeping existing virtual environment"
        echo ""
        echo "To activate: source $VENV_DIR/bin/activate"
        exit 0
    fi
fi

# Create virtual environment
print_step "Creating virtual environment..."
$PYTHON_CMD -m venv "$VENV_DIR"
print_success "Virtual environment created at $VENV_DIR"

# Activate and upgrade pip
print_step "Upgrading pip..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
print_success "Pip upgraded"

# Install requirements if they exist
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    print_step "Installing requirements..."
    pip install -r "$PROJECT_ROOT/requirements.txt" --quiet 2>/dev/null || true
    print_success "Requirements installed"
fi

# Install development dependencies
print_step "Installing development tools..."
pip install --quiet \
    black \
    flake8 \
    pytest \
    ipython \
    2>/dev/null || true
print_success "Development tools installed"

# Deactivate
deactivate

# Summary
print_header "Setup Complete! 🎉"

echo "Virtual environment location: $VENV_DIR"
echo ""
echo "To activate the virtual environment:"
echo -e "  ${GREEN}source .venv/bin/activate${NC}"
echo ""
echo "To deactivate:"
echo -e "  ${GREEN}deactivate${NC}"
echo ""
echo "To run the worker locally:"
echo "  source .venv/bin/activate"
echo "  python src/worker.py"
echo ""
echo "Installed packages:"
source "$VENV_DIR/bin/activate"
pip list --format=columns
deactivate
