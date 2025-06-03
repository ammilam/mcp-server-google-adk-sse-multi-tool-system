#!/bin/bash

# This script sets up the environment for the MCP server and Google ADK Agent.

set -e
# cleanup and then reactivate the virtual environment
deactivate 2>/dev/null || true
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install google-adk
pip install -e ./mcp_agent
npm install -prefix=mcp
