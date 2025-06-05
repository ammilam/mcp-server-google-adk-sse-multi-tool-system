from dotenv import load_dotenv
from google.adk.agents import Agent
import os
import logging

from .mcp_toolkit import get_toolkit

# Initialize the toolkit singleton - this ensures a session is created
toolkit = get_toolkit()

# Primary way to import tools from within the package
from .tools import (
    mcp_read_file,
    mcp_write_file,
    mcp_list_files,
    mcp_delete_file,
    mcp_get_weather,
    mcp_call_api,
    mcp_store_data,
    mcp_store_number,
    mcp_store_boolean,
    mcp_retrieve_data,
    mcp_clone_repository,
    mcp_list_repositories,
    mcp_analyze_repository,
    mcp_generate_readme
)
        
# Rename to root_agent for ADK compatibility
root_agent = Agent(
    name="mcp_agent",
    model="gemini-2.0-flash",
    description="Agent that can handle weather, time, and interact with a Model Control Protocol server",
    instruction="""I can help you with various tasks through my integration with the MCP server.
I can:
- Get current time in different cities
- Check weather conditions in locations
- Read, write, list, and delete files
- Make API calls to external services
- Store and retrieve data in a session (text, numbers, or boolean values)
- Clone and analyze code repositories from GitHub or GitLab
- Generate documentation for code repositories

When you ask me about files, I'll use the appropriate file operation tools.
When you ask me about weather, I'll look up the latest conditions.
When you want to store information for later, I'll use session storage.

For API calls:
- I'll need a complete URL (e.g., "api.example.com/endpoint" or "http://api.example.com/endpoint")
- I need to know which HTTP method to use (GET, POST, PUT, DELETE)
- For POST/PUT requests, I'll need the data to send
- I'll always ask you to confirm details before making potentially sensitive API calls

For repository operations:
- I can clone repositories from GitHub or GitLab
- I can analyze repositories and generate documentation
- I can list all cloned repositories

For example, you can ask me to:
- "Clone the repository at github.com/username/repo-name"
- "Analyze the code from the repository I just cloned"
- "Generate a README for the repository"
""",
    tools=[
        # Tools remain the same
        mcp_read_file,
        mcp_write_file,
        mcp_list_files,
        mcp_delete_file,
        
        # MCP API tools
        mcp_call_api,
        mcp_get_weather,
        
        # MCP session tools
        mcp_store_data,
        mcp_store_number, 
        mcp_store_boolean, 
        mcp_retrieve_data,

        # Repository tools
        mcp_clone_repository,
        mcp_list_repositories,
        mcp_analyze_repository,
        mcp_generate_readme,
    ]
)

# Keep 'agent' for backward compatibility if needed
agent = root_agent