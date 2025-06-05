#!/bin/bash

set -e

MODE=${1:-"web"}

# MODE can be web or run
if [ "$MODE" == "web" ]; then
    # Start the MCP server in web mode
   
    ARG=web
elif [ "$MODE" == "run" ]; then
    # Run the MCP agent
    ARG="run mcp_agent"
else
    echo "Invalid mode. Use 'web' or 'run'."
    exit 1
fi

cd mcp_agent

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
adk $ARG
