#!/bin/bash

set -e

# Start the MCP server
npm run start -prefix=mcp &
# Start the Google ADK Agent
./venv/bin/adk web
