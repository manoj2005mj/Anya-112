#!/bin/bash
# Installation script for server2 dependencies

echo "==================================="
echo "Installing server2 dependencies..."
echo "==================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python --version | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"
echo ""

# Install dependencies
echo "Installing from pyproject.toml..."
pip install -e . 2>&1 | tail -20

echo ""
echo "==================================="
echo "Installation complete!"
echo "==================================="
echo ""
echo "To run the server:"
echo "  python -m server2.main"
echo ""
echo "Server will run on: http://localhost:8000"
