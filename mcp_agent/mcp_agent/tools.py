import logging
import os
import time
from typing import Dict, Any, Optional, List  # Added List import here

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .mcp_toolkit import get_toolkit as _get_toolkit_internal

def get_toolkit_with_retry(max_retries=3, retry_delay=2):
    from .mcp_toolkit import get_toolkit
    
    for attempt in range(max_retries):
        try:
            toolkit = get_toolkit()
            # Test if session is active
            if toolkit.session_id:
                return toolkit
            else:
                logger.warning(f"No active session found (attempt {attempt+1}/{max_retries}), retrying...")
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Error initializing toolkit (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    # Return the toolkit instance even if session initialization failed
    return _get_toolkit_internal()

# Get singleton MCP toolkit instance with retry
mcp_toolkit = get_toolkit_with_retry()


# File System Tools
def mcp_read_file(file_path: str) -> dict:
    """Reads a file from the file system.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either file content or error message
    """
    try:
        # Ensure toolkit has active session
        if not mcp_toolkit.session_id:
            return {
                "status": "error",
                "error_message": "No active MCP session. Please try again."
            }
            
        result = mcp_toolkit.read_file(file_path)
        
        if result.get("success"):
            return {
                "status": "success",
                "content": result.get("data", "")
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error reading file")
            }
    except Exception as e:
        logger.error(f"Error in mcp_read_file: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_write_file(file_path: str, content: str) -> dict:
    """Writes content to a file.
    
    Args:
        file_path: Path where to write the file
        content: Content to write to the file
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and possibly an error message
    """
    try:
        result = mcp_toolkit.write_file(file_path, content)
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"File successfully written to {file_path}"
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error writing file")
            }
    except Exception as e:
        logger.error(f"Error in mcp_write_file: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_list_files(directory_path: str) -> dict:
    """Lists files in a directory.
    
    Args:
        directory_path: Path to the directory to list
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either file list or error message
    """
    try:
        result = mcp_toolkit.list_files(directory_path)
        
        if result.get("success"):
            return {
                "status": "success",
                "files": result.get("data", [])
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error listing files")
            }
    except Exception as e:
        logger.error(f"Error in mcp_list_files: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_delete_file(file_path: str) -> dict:
    """Deletes a file from the file system.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and possibly an error message
    """
    try:
        result = mcp_toolkit.delete_file(file_path)
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"File {file_path} successfully deleted"
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error deleting file")
            }
    except Exception as e:
        logger.error(f"Error in mcp_delete_file: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

# API Tools
def mcp_call_api(endpoint: str, method: str, data: Optional[Dict[str, Any]] = None, 
                headers: Optional[Dict[str, Any]] = None) -> dict:
    """Makes an API call through the MCP server.
    
    Args:
        endpoint: The URL to call (with or without http:// prefix)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data to send with the request
        headers: Optional headers to include in the request
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and response data or error message
    """
    try:
        # Ensure method is uppercase
        method = method.upper() if method else "GET"
        
        # Validate endpoint has protocol
        if endpoint and not (endpoint.startswith('http://') or endpoint.startswith('https://')):
            endpoint = 'http://' + endpoint
            
        logger.info(f"Making API call to {endpoint} with method {method}")
        
        # Don't send data for GET requests
        if method == "GET":
            data = None
            
        result = mcp_toolkit.call_api(endpoint, method, data, headers)
        
        if result.get("success"):
            return {
                "status": "success",
                "data": result.get("data", {})
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error making API call")
            }
    except Exception as e:
        logger.error(f"Error in mcp_call_api: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

# Repository Tools
def mcp_clone_repository(url: str) -> dict:
    """Clones a GitHub or GitLab repository.
    
    Args:
        url: Repository URL (GitHub or GitLab)
        
    Returns:
        dict: A dictionary with status and either repository path or error message
    """
    try:
        logger.info(f"Cloning repository from {url}")
        
        result = mcp_toolkit.execute_tool("repository", {
            "operation": "clone",
            "url": url
        })
        
        if result.get("success"):
            # Get the repo path from the result
            repo_path = result.get("data", {}).get("path", "")
            
            # Ensure the path includes data/repos for proper resolution
            if repo_path and not repo_path.startswith("data/repos/"):
                repo_path = f"data/repos/{os.path.basename(repo_path)}"
                
            return {
                "status": "success",
                "repo_path": repo_path,
                "repo_name": os.path.basename(repo_path) if repo_path else None,
                "message": result.get("data", {}).get("message", "Repository cloned successfully")
            }
        else:
            error_msg = result.get("error", "Unknown error cloning repository")
            return {
                "status": "error",
                "error_message": error_msg
            }
    except Exception as e:
        logger.error(f"Error in mcp_clone_repository: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_list_repositories() -> dict:
    """Lists available repositories.
    
    Returns:
        dict: A dictionary with status and list of repositories
    """
    try:
        result = mcp_toolkit.execute_tool("repository", {
            "operation": "list"
        })
        
        if result.get("success"):
            return {
                "status": "success",
                "repositories": result.get("data", [])
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error listing repositories")
            }
    except Exception as e:
        logger.error(f"Error in mcp_list_repositories: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_analyze_repository(repo_path: str) -> dict:
    """Analyzes a repository and provides information about its structure and contents.
    
    Args:
        repo_path: Path to the repository (should be the name or relative path within the repos directory)
        
    Returns:
        dict: A dictionary with status and repository analysis information
    """
    try:
        # Remove any leading slashes to ensure we're using relative paths
        clean_path = repo_path.lstrip('/')
        if clean_path.startswith('data/repos/'):
            # Remove the data/repos prefix if it's already there
            clean_path = clean_path.replace('data/repos/', '', 1)
        
        logger.info(f"Analyzing repository at path: {clean_path}")
        
        result = mcp_toolkit.execute_tool("repository", {
            "operation": "analyze",
            "path": clean_path
        })
        
        if result.get("success"):
            return {
                "status": "success",
                "analysis": result.get("data", {})
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error analyzing repository")
            }
    except Exception as e:
        logger.error(f"Error in mcp_analyze_repository: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_generate_readme(repo_path: str) -> dict:
    """Generates a README document for a repository.
    
    Args:
        repo_path: Path to the repository (should be the name or relative path within the repos directory)
        
    Returns:
        dict: A dictionary with status and generated README content
    """
    try:
        # Remove any leading slashes to ensure we're using relative paths
        clean_path = repo_path.lstrip('/')
        if clean_path.startswith('data/repos/'):
            # Remove the data/repos prefix if it's already there
            clean_path = clean_path.replace('data/repos/', '', 1)
        
        logger.info(f"Generating README for repository at path: {clean_path}")
        
        result = mcp_toolkit.execute_tool("repository", {
            "operation": "generate_readme",
            "path": clean_path
        })
        
        if result.get("success"):
            return {
                "status": "success",
                "readme_path": result.get("data", {}).get("path"),
                "content": result.get("data", {}).get("content")
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error generating README")
            }
    except Exception as e:
        logger.error(f"Error in mcp_generate_readme: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }
    
# Weather Tool
def mcp_get_weather(location: str) -> dict:
    """Gets weather information for a specified location.
    
    Args:
        location: The location to get weather for
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either weather report or error message
    """
    try:
        result = mcp_toolkit.get_weather(location)
        
        if result.get("success"):
            weather_data = result.get("data", {})
            return {
                "status": "success",
                "report": f"The weather in {location} is {weather_data.get('condition')} with a temperature of {weather_data.get('temperature')}. " +
                          f"Humidity is {weather_data.get('humidity')} and wind speed is {weather_data.get('windSpeed')}."
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", f"Weather information for '{location}' is not available.")
            }
    except Exception as e:
        logger.error(f"Error in mcp_get_weather: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

# Session Data Tools
def mcp_store_data(key: str, value: str) -> dict:
    """Stores data in the current session.
    
    Args:
        key: The key to store the data under
        value: The value to store (as a string)
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and possibly an error message
    """
    try:
        result = mcp_toolkit.set_session_data({key: value})
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"Data stored successfully with key: {key}"
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error storing data")
            }
    except Exception as e:
        logger.error(f"Error in mcp_store_data: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

# Add these new functions after mcp_store_data
def mcp_store_number(key: str, value: float) -> dict:
    """Stores a number in the current session.
    
    Args:
        key: The key to store the data under
        value: The numeric value to store
        
    Returns:
        dict: A dictionary with status information
    """
    try:
        result = mcp_toolkit.set_session_data({key: value})
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"Number {value} stored successfully with key: {key}"
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error storing number")
            }
    except Exception as e:
        logger.error(f"Error in mcp_store_number: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_store_boolean(key: str, value: bool) -> dict:
    """Stores a boolean value in the current session.
    
    Args:
        key: The key to store the data under
        value: The boolean value to store
        
    Returns:
        dict: A dictionary with status information
    """
    try:
        result = mcp_toolkit.set_session_data({key: value})
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"Boolean value {'true' if value else 'false'} stored successfully with key: {key}"
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error storing boolean value")
            }
    except Exception as e:
        logger.error(f"Error in mcp_store_boolean: {str(e)}")
        return {
            "status": "error", 
            "error_message": f"Exception: {str(e)}"
        }
        
def mcp_retrieve_data(key: str) -> dict:
    """Retrieves data from the current session.
    
    Args:
        key: The key to retrieve data for
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either the retrieved value or an error message
    """
    try:
        result = mcp_toolkit.get_session_data(key)
        
        if result.get("success"):
            return {
                "status": "success",
                "value": result.get("data")
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", f"No data found for key: {key}")
            }
    except Exception as e:
        logger.error(f"Error in mcp_retrieve_data: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }
    
def debug_gitlab_job(job_url: str, access_token: Optional[str] = None) -> dict:
    """Debugs a GitLab job by analyzing its trace logs and providing insights.
    
    This tool fetches trace logs from GitLab's API and analyzes them to identify
    errors, issues, and potential solutions. Works with both gitlab.com and 
    self-hosted GitLab instances.
    
    Args:
        job_url: The full URL of the GitLab job to debug
               (e.g., 'https://gitlab.com/group/project/-/jobs/1234567' or
                      'https://gitlab.example.com/group/project/-/jobs/1234567')
        access_token: Optional access token for private repositories
    
    Returns:
        dict: A comprehensive analysis of the job logs and suggested fixes
    """
    try:
        # Send request to MCP server
        result = mcp_toolkit.execute_tool("debug_gitlab_job", {
            "operation": "debug",
            "job_url": job_url,
            **({"access_token": access_token} if access_token else {})
        })

        if not result:
            logger.error("No result returned from debug_gitlab_job tool")
            return {
                "status": "error",
                "error_message": "No result returned from debug_gitlab_job tool"
            }
        
        if not result.get("success"):
            logger.error(f"Error debugging GitLab job: {result.get('error', 'Unknown error')}")
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error debugging GitLab job")
            }
            
        # Process the data but leave most analysis to be done dynamically by the LLM
        data = result.get("data", {})
        raw_logs = data.get("raw_logs", "")
        analysis = data.get("analysis", {})
        job_metadata = analysis.get("gitlab_job_metadata", {})
        
        # Extract GitLab instance information
        gitlab_instance = data.get("gitlab_instance", "Unknown GitLab instance")
        project_path = data.get("project_path", "Unknown project")
        
        # Provide basic information from the server for the agent to analyze
        return {
            "status": "success",
            "job_url": data.get("job_url"),
            "gitlab_instance": gitlab_instance,
            "project_path": project_path,
            "job_metadata": {
                "id": job_metadata.get("id"),
                "status": job_metadata.get("status"),
                "stage": job_metadata.get("stage"),
                "name": job_metadata.get("name"),
                "ref": job_metadata.get("ref"),
                "started_at": job_metadata.get("started_at"),
                "finished_at": job_metadata.get("finished_at"),
                "duration": job_metadata.get("duration"),
            },
            "error_stats": {
                "error_count": analysis.get("error_count", 0),
                "warning_count": analysis.get("warning_count", 0),
                "exit_code": analysis.get("exit_code"),
                "log_length": analysis.get("log_length", 0)
            },
            "error_samples": analysis.get("errors", []),
            "warning_samples": analysis.get("warnings", []),
            "identified_issues": analysis.get("identified_issues", []),
            "root_causes": analysis.get("root_causes", []),
            "suggestions": analysis.get("suggestions", []),
            "contextual_analysis": analysis.get("contextual_analysis", {}),
            "raw_logs": raw_logs  # Include raw logs for the agent to analyze
        }
    except Exception as e:
        logger.error(f"Error in debug_gitlab_job: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }
        
def mcp_git(operation: str, repo_path: str, **kwargs) -> dict:
    """Performs Git operations on a repository.
    
    This tool allows creating branches, committing changes, pushing to remote repositories,
    and other Git operations on cloned repositories.
    
    Args:
        operation: The Git operation to perform ('create_branch', 'checkout_branch', 'commit', 'push', 'status', 'pull')
        repo_path: Path to the repository (should be the name or relative path within the repos directory)
        **kwargs: Additional arguments depending on the operation:
            - branch: Branch name for branch operations
            - message: Commit message for commit operations
            - files: List of files to commit (optional, commits all changes if not specified)
            - credentials: Dict with 'token' or 'username'/'password' for push operations
    
    Returns:
        dict: A dictionary with status information and operation results
    """
    try:
        # Prepare parameters based on the operation
        params = {
            "operation": operation,
            "repoPath": repo_path
        }
        
        # Add optional parameters
        if "branch" in kwargs and kwargs["branch"]:
            params["branch"] = kwargs["branch"]
            
        if "message" in kwargs and kwargs["message"]:
            params["message"] = kwargs["message"]
            
        if "files" in kwargs and kwargs["files"]:
            params["files"] = kwargs["files"]
            
        if "remote" in kwargs and kwargs["remote"]:
            params["remote"] = kwargs["remote"]
            
        if "credentials" in kwargs and kwargs["credentials"]:
            params["credentials"] = kwargs["credentials"]
            
        # Execute the Git tool
        result = mcp_toolkit.execute_tool("git", params)
        
        if result.get("success"):
            return {
                "status": "success",
                "operation": operation,
                "result": result.get("data", {})
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", f"Unknown error performing Git {operation}")
            }
    except Exception as e:
        logger.error(f"Error in mcp_git: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_terraform(operation: str, working_dir: str, options: Optional[List[str]] = None, 
                 auto_approve: bool = False, variables: Optional[Dict[str, str]] = None) -> dict:
    """Runs Terraform commands on a working directory.
    
    This tool enables running various Terraform operations like init, plan, apply,
    validate, fmt, etc. on Terraform code in the specified directory.
    
    Args:
        operation: Terraform operation ('init', 'plan', 'apply', 'validate', 'fmt', 'output', 'destroy')
        working_dir: Directory containing Terraform code
        options: Optional list of command-line options to pass to Terraform
        auto_approve: Whether to automatically approve apply/destroy operations
        variables: Optional dictionary of Terraform variables to pass to the command
    
    Returns:
        dict: A dictionary with status information and command output
    """
    try:
        params = {
            "operation": operation,
            "workingDir": working_dir,
            "autoApprove": auto_approve
        }
        
        if options:
            params["options"] = options
            
        if variables:
            params["variables"] = variables
        
        result = mcp_toolkit.execute_tool("terraform", params)
        
        if result.get("success"):
            output = result.get("data", {}).get("output", "")
            return {
                "status": "success",
                "operation": operation,
                "output": output
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", f"Error executing terraform {operation}")
            }
    except Exception as e:
        logger.error(f"Error in mcp_terraform: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_terraform_add_resource(
    repo_path: str, 
    resource_type: str,
    resource_name: str, 
    attributes: Dict[str, Any], 
    branch_name: Optional[str] = None, 
    commit_message: Optional[str] = None,
    file_name: Optional[str] = None
) -> dict:
    """Adds a new Terraform resource to a repository and commits the changes.
    
    This function creates or modifies a Terraform file in the appropriate directory
    of a repository, adds a new resource of the specified type, and commits the changes.
    
    Args:
        repo_path: Path to the repository (name or path)
        resource_type: Type of Terraform resource to create (e.g., 'google_project')
        resource_name: Name for the resource (e.g., 'my_project')
        attributes: Dictionary of attributes for the resource
        branch_name: Optional branch name to create for the changes
        commit_message: Optional commit message (default: generate appropriate message)
        file_name: Optional specific file name to create or modify
        
    Returns:
        dict: Status information about the operation
    """
    try:
        # 1. Clean and validate repository path
        repo_path = _clean_repo_path(repo_path)
        
        # 2. Create branch if specified
        if branch_name:
            branch_result = mcp_git("create_branch", repo_path, branch=branch_name)
            if branch_result.get("status") != "success":
                return {
                    "status": "error",
                    "error_message": f"Failed to create branch: {branch_result.get('error_message', 'Unknown error')}"
                }
            
            # Checkout the branch to ensure we're working on it
            checkout_result = mcp_git("checkout_branch", repo_path, branch=branch_name)
            if checkout_result.get("status") != "success":
                return {
                    "status": "error",
                    "error_message": f"Failed to checkout branch: {checkout_result.get('error_message', 'Unknown error')}"
                }
        
        # 3. Find or determine appropriate location for the Terraform file
        repo_full_path = f"data/repos/{repo_path}"
        if not file_name:
            file_name = f"{resource_type.split('_')[-1]}.tf"
        
        # First check if there's an existing file with similar name
        find_result = mcp_find_files(repo_path, f"*{file_name}")
        
        if find_result.get("status") == "success" and find_result.get("count", 0) > 0:
            # Use the first matching file
            target_file = find_result.get("files")[0]
            # Extract relative path within repository
            if target_file.startswith(repo_full_path):
                relative_path = target_file[len(repo_full_path) + 1:]
            else:
                # Just use the filename if we can't determine relative path
                relative_path = os.path.basename(target_file)
        else:
            # Search for other .tf files to determine best location
            tf_result = mcp_find_files(repo_path, "*.tf")
            
            if tf_result.get("status") == "success" and tf_result.get("count", 0) > 0:
                # Use the directory of the first found .tf file
                first_tf = tf_result.get("files")[0]
                dir_path = os.path.dirname(first_tf)
                if dir_path.startswith(repo_full_path):
                    relative_dir = dir_path[len(repo_full_path) + 1:]
                else:
                    relative_dir = ""
                relative_path = os.path.join(relative_dir, file_name)
            else:
                # No existing .tf files, use repo root
                relative_path = file_name
        
        # 4. Create or update the Terraform file
        target_path = os.path.join(repo_full_path, relative_path)
        
        # Check if file exists
        file_exists = False
        try:
            read_result = mcp_read_file(target_path)
            file_exists = read_result.get("status") == "success"
            existing_content = read_result.get("content", "")
        except:
            existing_content = ""
            
        # Format the resource attributes into Terraform syntax
        resource_content = format_terraform_resource(resource_type, resource_name, attributes)
        
        # Combine with existing content or create new file
        if file_exists:
            # Ensure newlines between resources
            new_content = f"{existing_content.rstrip()}\n\n{resource_content}\n"
        else:
            new_content = f"{resource_content}\n"
        
        # Write the file
        write_result = mcp_write_file(target_path, new_content)
        
        if write_result.get("status") != "success":
            return {
                "status": "error",
                "error_message": f"Failed to write Terraform file: {write_result.get('error_message', 'Unknown error')}"
            }
        
        # 5. Format the Terraform code
        dir_path = os.path.dirname(target_path)
        if not dir_path:
            dir_path = repo_full_path
            
        # Try to format but don't fail if formatting fails
        try:
            mcp_terraform_fmt(dir_path)
        except Exception as e:
            logger.warning(f"Terraform formatting failed: {str(e)}")
        
        # 6. Commit the changes
        if commit_message is None:
            resource_name_clean = resource_name.replace("_", " ").title()
            commit_message = f"feat: add {resource_type} resource for {resource_name_clean}"
        
        # Get the relative path for the commit
        if target_path.startswith(repo_full_path):
            commit_path = target_path[len(repo_full_path) + 1:]
        else:
            commit_path = os.path.basename(target_path)
            
        commit_result = mcp_git("commit", repo_path, message=commit_message, files=[commit_path])
        
        if commit_result.get("status") != "success":
            return {
                "status": "error",
                "error_message": f"Failed to commit changes: {commit_result.get('error_message', 'Unknown error')}",
                "file_path": target_path
            }
        
        # 7. Return success with details
        return {
            "status": "success",
            "message": f"Successfully added {resource_type} resource '{resource_name}' and committed changes",
            "file_path": target_path,
            "relative_path": commit_path,
            "branch": branch_name,
            "commit": commit_result.get("result")
        }
    except Exception as e:
        logger.error(f"Error in mcp_terraform_add_resource: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

# Helper function to clean repository path
def _clean_repo_path(repo_path: str) -> str:
    """Cleans and normalizes repository path"""
    if not repo_path:
        raise ValueError("Repository path is required")
        
    # If it includes data/repos, extract just the repo name
    if "data/repos/" in repo_path:
        parts = repo_path.split("data/repos/")
        return parts[-1]
    
    # If it's a full path, extract just the last part
    if "/" in repo_path:
        return os.path.basename(repo_path)
        
    return repo_path

# Helper function to format Terraform resource content
def format_terraform_resource(resource_type: str, resource_name: str, attributes: Dict[str, Any]) -> str:
    """Formats a Terraform resource definition with proper indentation"""
    lines = [f'resource "{resource_type}" "{resource_name}" {{']
    
    # Format each attribute with proper indentation
    for key, value in attributes.items():
        if isinstance(value, dict):
            # Handle nested blocks
            lines.append(f'  {key} {{')
            for sub_key, sub_value in value.items():
                lines.append(f'    {sub_key} = {format_terraform_value(sub_value)}')
            lines.append('  }')
        else:
            # Handle simple attributes
            lines.append(f'  {key} = {format_terraform_value(value)}')
            
    lines.append('}')
    
    return '\n'.join(lines)

# Helper function to format Terraform values
def format_terraform_value(value: Any) -> str:
    """Formats a Python value as a Terraform value"""
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # Check if it's a reference and shouldn't be quoted
        if (value.startswith('var.') or 
            value.startswith('local.') or 
            value.startswith('module.') or 
            value.startswith('${') or
            value.startswith('terraform.')):
            return value
        else:
            return f'"{value}"'
    elif isinstance(value, list):
        if not value:
            return "[]"
        elif all(isinstance(x, str) for x in value):
            return '[' + ', '.join(f'"{x}"' for x in value) + ']'
        else:
            return '[' + ', '.join(format_terraform_value(x) for x in value) + ']'
    elif isinstance(value, dict):
        return '{' + ', '.join(f'{k} = {format_terraform_value(v)}' for k, v in value.items()) + '}'
    elif value is None:
        return 'null'
    else:
        return str(value)
    
def mcp_terraform_fmt(working_dir: str, recursive: bool = True) -> dict:
    """Formats Terraform code using terraform fmt.
    
    This is a convenience function that calls terraform fmt with recursive option
    to format all Terraform files in the directory tree.
    
    Args:
        working_dir: Directory containing Terraform code
        recursive: Whether to recursively format subdirectories
    
    Returns:
        dict: A dictionary with status information and command output
    """
    options = ["-recursive"] if recursive else []
    return mcp_terraform("fmt", working_dir, options=options)

def mcp_write_terraform_file(file_path: str, content: str, auto_find_path: bool = True) -> dict:
    """Writes a Terraform file and automatically formats it.
    
    This enhanced function will attempt to find the correct location for Terraform files
    if the specified path doesn't exist or isn't accessible.
    
    Args:
        file_path: Path to the Terraform file to write
        content: Terraform configuration content
        auto_find_path: Whether to automatically find an appropriate path if the specified one doesn't work
    
    Returns:
        dict: A dictionary with status information
    """
    try:
        # Make sure file_path has proper extension
        if not file_path.endswith('.tf'):
            file_path = f"{file_path}.tf"
            
        # First check if this is a repo path and ensure correct format
        if 'repos/' in file_path:
            # Extract repo name from path
            parts = file_path.split('repos/')
            if len(parts) > 1:
                repo_path = parts[1].split('/')[0]
                # Check if the file path seems to be missing subdirectories
                if '/' not in parts[1] and repo_path != file_path:
                    # Default to an infra directory
                    file_path = f"repos/{repo_path}/infra/{os.path.basename(file_path)}"
                    logger.info(f"Adjusted file path to include infra directory: {file_path}")
        
        # First try to write to the specified path
        write_result = mcp_write_file(file_path, content)
        
        if write_result.get("status") == "success":
            # Get the directory containing the file
            dir_path = os.path.dirname(file_path)
            if not dir_path:
                dir_path = "."
            
            # Run terraform fmt on the file
            fmt_result = mcp_terraform("fmt", dir_path, options=[os.path.basename(file_path)])
            
            if fmt_result.get("status") != "success":
                return {
                    "status": "warning",
                    "message": f"File written successfully but formatting failed: {fmt_result.get('error_message')}",
                    "file_path": file_path
                }
            
            return {
                "status": "success",
                "message": "Terraform file written and formatted successfully",
                "file_path": file_path
            }
        
        # If auto_find_path is enabled and writing failed, try to find a better path
        if auto_find_path:
            # Extract repo_path from file_path - assuming file_path is relative to the repo
            parts = file_path.split('/')
            repo_idx = -1
            
            try:
                repo_idx = parts.index('repos')
            except ValueError:
                # If 'repos' not in parts, try a different approach
                pass
                
            if repo_idx >= 0 and repo_idx + 1 < len(parts):
                repo_name = parts[repo_idx + 1]
                repo_path = '/'.join(parts[:repo_idx + 2])
                
                # Get just the filename
                filename = os.path.basename(file_path)
                
                # Try to find an appropriate path
                path_result = mcp_ensure_file_path(repo_path, filename, "terraform")
                
                if path_result.get("status") == "success":
                    new_path = path_result.get("file_path")
                    
                    # Try writing to the new path
                    new_write_result = mcp_write_file(new_path, content)
                    
                    if new_write_result.get("status") == "success":
                        # Format the new file
                        new_dir_path = os.path.dirname(new_path)
                        if not new_dir_path:
                            new_dir_path = "."
                        
                        fmt_result = mcp_terraform("fmt", new_dir_path, options=[os.path.basename(new_path)])
                        
                        return {
                            "status": "success",
                            "message": f"Terraform file written to alternative path and formatted successfully",
                            "file_path": new_path,
                            "original_path": file_path
                        }
            
            # If we couldn't determine a better path or writing still failed
            return {
                "status": "error",
                "error_message": f"Failed to write file to {file_path} and couldn't find alternative location",
                "original_error": write_result.get("error_message")
            }
        
        # If auto_find_path is disabled, just return the original error
        return write_result
    except Exception as e:
        logger.error(f"Error in mcp_write_terraform_file: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_create_feature_branch(repo_path: str, feature_name: str) -> dict:
    """Creates a new feature branch in a repository.
    
    This is a convenience function that creates a properly named feature branch
    following git flow conventions (feature/name-of-feature).
    
    Args:
        repo_path: Path to the repository
        feature_name: Name of the feature (will be sanitized for branch naming)
    
    Returns:
        dict: A dictionary with status information
    """
    try:
        # Sanitize feature name for branch
        import re
        sanitized_name = re.sub(r'[^a-zA-Z0-9-_]', '-', feature_name.lower()).strip('-')
        branch_name = f"feature/{sanitized_name}"
        
        # Create the branch
        return mcp_git("create_branch", repo_path, branch=branch_name)
    except Exception as e:
        logger.error(f"Error in mcp_create_feature_branch: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }
        
def mcp_find_files(repo_path: str, file_pattern: str) -> dict:
    """Find files in a repository matching a pattern.
    
    This tool searches through a cloned repository and finds files that match 
    the specified pattern. It's useful when you need to locate specific files
    but don't know their exact location in the repository.
    
    Args:
        repo_path: Path to the repository (should be the name or relative path within the repos directory)
        file_pattern: File pattern to search for (e.g., "*.tf", "main.py", etc.)
    
    Returns:
        dict: A dictionary with matching files and related information
    """
    try:
        params = {
            "operation": "find",
            "repoPath": repo_path,
            "filePattern": file_pattern
        }
        
        result = mcp_toolkit.execute_tool("git", params)
        
        if result.get("success"):
            files = result.get("data", {}).get("matchingFiles", [])
            count = result.get("data", {}).get("count", 0)
            repo_path = result.get("data", {}).get("repoPath", "")
            
            return {
                "status": "success",
                "files": files,
                "count": count,
                "repo_path": repo_path
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error searching for files")
            }
    except Exception as e:
        logger.error(f"Error in mcp_find_files: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_ensure_file_path(repo_path: str, file_path: str, file_type: Optional[str] = None) -> dict:
    """Ensures a file path exists or suggests an appropriate one.
    
    This tool helps find the correct location for a file in a repository.
    If the file exists, it returns its path. If not, it suggests a suitable
    location based on common conventions and repository structure.
    
    Args:
        repo_path: Path to the repository
        file_path: Tentative file path to check or create
        file_type: Type of file (e.g., 'terraform', 'python', 'config')
    
    Returns:
        dict: Information about the file path
    """
    try:
        # First check if the file exists at the exact path
        exact_path = os.path.join(repo_path, file_path)
        existing_file_result = mcp_toolkit.execute_tool("file_system", {
            "operation": "read",
            "path": exact_path
        })
        
        if existing_file_result.get("success"):
            # File exists at the specified path
            return {
                "status": "success",
                "exists": True,
                "file_path": exact_path,
                "content": existing_file_result.get("data")
            }
        
        # File doesn't exist, try to find related files
        pattern = "*" + os.path.basename(file_path)
        related_files = mcp_find_files(repo_path, pattern)
        
        if related_files.get("status") == "success" and related_files.get("count") > 0:
            # Found similar files, suggest one of them
            suggested_path = related_files.get("files")[0]
            return {
                "status": "success",
                "exists": False,
                "file_path": suggested_path,
                "suggested_paths": related_files.get("files"),
                "message": f"File not found at {exact_path}, but similar files exist"
            }
        
        # No similar files found, suggest a path based on file type
        suggested_path = ""
        if file_type == "terraform":
            # Search for any .tf files to find terraform directories
            tf_files = mcp_find_files(repo_path, "*.tf")
            if tf_files.get("status") == "success" and tf_files.get("count") > 0:
                # Use the directory of the first tf file
                tf_dir = os.path.dirname(tf_files.get("files")[0])
                suggested_path = os.path.join(tf_dir, os.path.basename(file_path))
            else:
                # Default terraform structure
                suggested_path = os.path.join(repo_path, "infra", os.path.basename(file_path))
        elif file_type == "python":
            # Default to a src directory for Python files
            suggested_path = os.path.join(repo_path, "src", os.path.basename(file_path))
        else:
            # General case - use the repository root
            suggested_path = os.path.join(repo_path, os.path.basename(file_path))
        
        # Generate a unique file path if needed
        if not suggested_path:
            # Default fallback - use a timestamp to ensure uniqueness
            import time
            timestamp = int(time.time())
            suggested_path = os.path.join(repo_path, f"{timestamp}_{os.path.basename(file_path)}")
        
        return {
            "status": "success",
            "exists": False,
            "file_path": suggested_path,
            "message": f"Suggested new file path: {suggested_path}"
        }
    except Exception as e:
        logger.error(f"Error in mcp_ensure_file_path: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }

def mcp_write_terraform_file(file_path: str, content: str, auto_find_path: bool = True) -> dict:
    """Writes a Terraform file and automatically formats it.
    
    This enhanced function will attempt to find the correct location for Terraform files
    if the specified path doesn't exist or isn't accessible.
    
    Args:
        file_path: Path to the Terraform file to write
        content: Terraform configuration content
        auto_find_path: Whether to automatically find an appropriate path if the specified one doesn't work
    
    Returns:
        dict: A dictionary with status information
    """
    try:
        # First try to write to the specified path
        write_result = mcp_write_file(file_path, content)
        
        if write_result.get("status") == "success":
            # File written successfully, now format it
            dir_path = os.path.dirname(file_path)
            if not dir_path:
                dir_path = "."
            
            fmt_result = mcp_terraform("fmt", dir_path, options=[os.path.basename(file_path)])
            
            if fmt_result.get("status") != "success":
                return {
                    "status": "warning",
                    "message": f"File written successfully but formatting failed: {fmt_result.get('error_message')}",
                    "file_path": file_path
                }
            
            return {
                "status": "success",
                "message": "Terraform file written and formatted successfully",
                "file_path": file_path
            }
        
        # If auto_find_path is enabled and writing failed, try to find a better path
        if auto_find_path:
            # Extract repo_path from file_path - assuming file_path is relative to the repo
            # This is a simplification - in practice, we might need more sophisticated path extraction
            parts = file_path.split('/')
            if len(parts) > 2 and 'repos' in parts:
                repo_idx = parts.index('repos')
                if repo_idx + 1 < len(parts):
                    repo_name = parts[repo_idx + 1]
                    repo_path = '/'.join(parts[:repo_idx + 2])
                    
                    # Get just the filename
                    filename = os.path.basename(file_path)
                    
                    # Try to find an appropriate path
                    path_result = mcp_ensure_file_path(repo_path, filename, "terraform")
                    
                    if path_result.get("status") == "success":
                        new_path = path_result.get("file_path")
                        
                        # Try writing to the new path
                        new_write_result = mcp_write_file(new_path, content)
                        
                        if new_write_result.get("status") == "success":
                            # Format the new file
                            new_dir_path = os.path.dirname(new_path)
                            if not new_dir_path:
                                new_dir_path = "."
                            
                            fmt_result = mcp_terraform("fmt", new_dir_path, options=[os.path.basename(new_path)])
                            
                            return {
                                "status": "success",
                                "message": f"Terraform file written to alternative path and formatted successfully",
                                "file_path": new_path,
                                "original_path": file_path
                            }
            
            # If we couldn't determine a better path or writing still failed
            return {
                "status": "error",
                "error_message": f"Failed to write file to {file_path} and couldn't find alternative location",
                "original_error": write_result.get("error_message")
            }
        
        # If auto_find_path is disabled, just return the original error
        return write_result
    except Exception as e:
        logger.error(f"Error in mcp_write_terraform_file: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }