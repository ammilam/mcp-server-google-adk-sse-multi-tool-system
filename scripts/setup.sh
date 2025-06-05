#!/bin/bash

set -e

# Create a virtual environment and install the Python package
cd mcp_agent
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
cd ..
# Install Node.js dependencies
npm install -prefix mcp
