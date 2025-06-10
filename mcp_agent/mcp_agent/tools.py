import logging
import os
import time
from typing import Dict, Any, Optional

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
            return {
                "status": "success",
                "repo_path": result.get("data", {}).get("path"),
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
        