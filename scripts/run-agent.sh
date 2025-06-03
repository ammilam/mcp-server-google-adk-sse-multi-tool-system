#!/bin/bash

set -e

deactivate 2>/dev/null || true
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install google-adk
cd mcp_agent
pip install -e .
cd ..
adk web
