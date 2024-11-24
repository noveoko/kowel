#!/bin/bash
# lint.sh

# Run black
echo "Running Black..."
black .

# Run flake8
echo "Running Flake8..."
flake8 .

# Run mypy
echo "Running MyPy..."
mypy src/