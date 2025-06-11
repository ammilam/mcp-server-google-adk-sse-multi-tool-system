from dotenv import load_dotenv
from google.adk.agents import Agent
import os
import logging
from google.adk.tools import agent_tool
from google.adk.tools import google_search
from google.adk.code_executors import BuiltInCodeExecutor

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
    mcp_generate_readme,
    debug_gitlab_job,
    mcp_git,
    mcp_terraform,
    mcp_terraform_fmt,
    mcp_write_terraform_file,
    mcp_create_feature_branch,
    mcp_find_files,
    mcp_ensure_file_path,
    # Add the new function
    mcp_terraform_add_resource
)

search_agent = Agent(
    model='gemini-2.0-flash',
    name='SearchAgent',
    instruction="""
    You're a specialist in Google Search
    """,
    tools=[google_search],
)

coding_agent = Agent(
    model='gemini-2.0-flash',
    name='CodeAgent',
    instruction="""
    You're a specialist in Code Execution
    """,
code_executor=BuiltInCodeExecutor(),
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
- Debug and analyze GitLab CI/CD job failures

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

When you ask me about GitLab job failures, I can:
- Analyze job trace logs from GitLab.com or any self-hosted GitLab instance
- Identify failure patterns and root causes across various technologies
- Provide tailored advice for infrastructure, cloud deployments, and application builds
- Suggest specific solutions based on the actual errors in your logs
- Explain why the job failed and how to fix it in detail

For example, you can ask me:
- "Debug this GitLab job: https://gitlab.com/group/project/-/jobs/123456"
- "What's wrong with this pipeline job: https://gitlab.example.com/group/project/-/jobs/123456"
- "Help me fix the failures in this self-hosted GitLab job: https://gitlab.internal.company.com/group/project/-/jobs/123456"

For repository operations:
- I can clone repositories from GitHub or GitLab
- I can analyze repositories and generate documentation
- I can list all cloned repositories
- I can create feature branches, make commits, and push changes
- I can write and format Terraform code for infrastructure as code

For Terraform operations:
- I can create Terraform files with proper formatting in the appropriate directories
- I can analyze existing Terraform code to understand your infrastructure
- I can run terraform commands like init, plan, apply, validate, and terraform fmt --recursive
- I can help create resources that reference existing infrastructure
- I can suggest improvements to your infrastructure code
- I can add new Terraform resources to existing repositories and commit the changes

For example, you can ask me to:
- "Find all Terraform files in my repository"
- "Create a feature branch for adding a new BigQuery dataset"
- "Write Terraform code for a GCP BigQuery dataset"
- "Format the Terraform code in my repository"
- "Commit my changes with a descriptive message"
- "Push my feature branch to GitHub"
- "Add a google_project resource to my repository and commit the changes"
""",
    tools=[
        agent_tool.AgentTool(agent=search_agent),
        agent_tool.AgentTool(agent=coding_agent),
        mcp_read_file,
        mcp_write_file,
        mcp_list_files,
        mcp_delete_file,
        mcp_find_files,
        mcp_ensure_file_path,
        
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

        # debug gitlab tools
        debug_gitlab_job,
        
        # IaC and Git tools
        mcp_git,
        mcp_terraform,
        mcp_terraform_fmt,
        mcp_write_terraform_file,
        mcp_create_feature_branch,
        mcp_terraform_add_resource,
    ]
)

# Keep 'agent' for backward compatibility if needed
agent = root_agent