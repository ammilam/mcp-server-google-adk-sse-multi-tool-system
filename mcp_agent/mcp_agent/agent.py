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
    You can help with:
    - Executing code snippets
    - Running code to solve programming problems
    - Debugging code issues
    - Analyzing code for correctness
    - Providing code examples and explanations
    """,
code_executor=BuiltInCodeExecutor(),
)

filesystem_agent = Agent(
    model='gemini-2.5-flash',
    name='FileSystemAgent',
    instruction="""
    You're a specialist in File System Operations
    You can help with:
    - Reading files from the file system
    - Writing files to the file system
    - Listing files in directories
    - Deleting files from the file system
    - Finding files in the file system
    - Ensuring file paths exist
    You can perform file operations using the following tools:
    - mcp_read_file: Read the contents of a file
    - mcp_write_file: Write data to a file
    - mcp_list_files: List files in a directory
    - mcp_delete_file: Delete a file
    - mcp_find_files: Find files matching a pattern
    - mcp_ensure_file_path: Ensure a file path exists
    """,
    tools=[
        mcp_read_file,
        mcp_write_file,
        mcp_list_files,
        mcp_delete_file,
        mcp_find_files,
        mcp_ensure_file_path,
    ],
)

api_agent = Agent(
    model='gemini-2.5-flash',
    name='ApiAgent',
    instruction="""
    You're a specialist in API Calls
    You can help with:
    - Making API calls to external services
    - Fetching weather data for locations
    - Calling APIs with GET, POST, PUT, DELETE methods
    - Handling API responses and errors
    You can make API calls using the following tools:
    - mcp_call_api: Make API calls to external services
    - mcp_get_weather: Get current weather conditions for a location
    """,
    tools=[
        mcp_call_api,
        mcp_get_weather,
    ],
)

# Session storage agent
session_agent = Agent(
    model='gemini-2.5-flash',
    name='SessionAgent',
    instruction="""
    You're a specialist in Session Storage
    You can help with:
    - Storing and retrieving text data
    - Storing and retrieving numbers
    - Storing and retrieving boolean values
    - Managing session data for later use
    You can store data in the session using the following tools:
    - mcp_store_data: Store text data
    - mcp_store_number: Store a number
    - mcp_store_boolean: Store a boolean value
    - mcp_retrieve_data: Retrieve stored data
    You can retrieve data from the session using the following tool:
    - mcp_retrieve_data: Retrieve stored data
    """,
    tools=[
        mcp_store_data,
        mcp_store_number,
        mcp_store_boolean,
        mcp_retrieve_data,
    ],
)

cloud_engineer_agent = Agent(
    model='gemini-2.5-flash',
    name='CloudEngineerAgent',
    instruction="""
    You are a specialist in Google Cloud Platform, CICD, Gitlab, and Terraform.
    You can help with:
    - Analyzing GitLab CI/CD job failures
    - Debugging and fixing issues in GitLab pipelines
    - Writing and formatting Terraform code
    - Creating and managing feature branches in Git repositories
    - Cloning and analyzing code repositories
    - Generating documentation for code repositories
    - Writing Terraform files for infrastructure as code
    - Adding new resources to existing Terraform configurations
    - Ensuring proper formatting and structure in Terraform files
    - Creating feature branches for new infrastructure changes
    - Pushing changes to Git repositories
    - Analyzing code repositories for best practices and improvements
    - Debugging GitLab job failures by analyzing job trace logs
    - Providing tailored advice for infrastructure, cloud deployments, and application builds
    - Suggesting specific solutions based on actual errors in your logs
    - Explaining why the job failed and how to fix it in detail
    - Cloning down the repository and analyzing the code to provide more context
    - Writing Terraform code for GCP resources like BigQuery datasets, Cloud Storage buckets, etc.
    - Using lowercase when styling commit messages, e.g., fix: fix variable misconfiguration
    - Creating feature branches using conventional branch names using lowercase characters and dashes '-' prefixed with: feat/ fix/ chore/ test/ ci/ docs/
    """,
    tools=[
        mcp_clone_repository,
        mcp_list_repositories,
        mcp_git,
        mcp_analyze_repository,
        mcp_generate_readme,
        debug_gitlab_job,
        mcp_terraform_fmt,
        mcp_write_terraform_file,
        mcp_create_feature_branch,
        mcp_terraform_add_resource,
        mcp_find_files,
        mcp_ensure_file_path,
    ]
)
    
# Rename to root_agent for ADK compatibility
root_agent = Agent(
    name="mcp_agent",
    model="gemini-2.5-flash",
    description="Agent that can handle weather, time, and interact with a Model Control Protocol server",
    instruction="""You can help with various tasks through your integration with an MCP server.
You can do the following:
- Get current time in different cities
- Check weather conditions in locations
- Read, write, list, and delete files
- Make API calls to external services
- Store and retrieve data in a session (text, numbers, or boolean values)
- Clone and analyze code repositories from GitHub or GitLab
- Generate documentation for code repositories
- Debug and analyze GitLab CI/CD job failures
- Use agent tools for interacting with tools and the MCP server

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
- Clone down the repository and analyze the code to provide more context

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
- Use lowercase when styling commit messages, e.g., fix: fix variable misconfiguration

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
        agent_tool.AgentTool(agent=filesystem_agent),
        agent_tool.AgentTool(agent=api_agent),
        agent_tool.AgentTool(agent=session_agent),
        agent_tool.AgentTool(agent=cloud_engineer_agent),
        
        # MCP API tools
        # mcp_call_api,
        # mcp_get_weather,
        
        # MCP session tools
        # mcp_store_data,
        # mcp_store_number, 
        # mcp_store_boolean, 
        # mcp_retrieve_data,

        # Repository tools
        # mcp_clone_repository,
        # mcp_list_repositories,
        # mcp_analyze_repository,
        # mcp_generate_readme,

        # debug gitlab tools
        # debug_gitlab_job,
        
        # IaC and Git tools
        # mcp_git,
        # mcp_terraform,
        # mcp_terraform_fmt,
        # mcp_write_terraform_file,
        # mcp_create_feature_branch,
        # mcp_terraform_add_resource,
    ]
)

# Keep 'agent' for backward compatibility if needed
agent = root_agent