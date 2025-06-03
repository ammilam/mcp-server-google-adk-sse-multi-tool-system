from google.adk.agents import Agent
import logging

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
    mcp_retrieve_data
)


# Make sure to update the tools list:
agent = Agent(
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

When you ask me about files, I'll use the appropriate file operation tools.
When you ask me about weather, I'll look up the latest conditions.
When you want to store information for later, I'll use session storage.
""",
    tools=[

        # MCP file system tools
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
        mcp_retrieve_data
    ]
)