import logging
from typing import Dict, Any, Optional
from .mcp_toolkit import get_toolkit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get singleton MCP toolkit instance
mcp_toolkit = get_toolkit()

# File System Tools
def mcp_read_file(file_path: str) -> dict:
    """Reads a file from the file system.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either file content or error message
    """
    try:
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