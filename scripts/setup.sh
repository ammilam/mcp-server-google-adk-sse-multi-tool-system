#!/bin/bash

set -e

rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install google-adk
pip install -e mcp_agent
npm install -prefix mcp
