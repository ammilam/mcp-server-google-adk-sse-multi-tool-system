import requests
import json
import uuid
import logging
from typing import Dict, Any, Optional, Callable, List
import threading
import sseclient
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MCP-Toolkit')

class MCPToolkit:
    """Client library to interact with MCP Server"""
    
    def __init__(self, mcp_server_url: Optional[str] = None):
        """
        Initialize the MCP Toolkit
        
        Args:
            mcp_server_url: Base URL of the MCP server, defaults to environment variable
        """
        self.mcp_server_url = mcp_server_url or os.environ.get("MCP_SERVER_URL", "http://localhost:8080")
        self.mcp_server_url = self.mcp_server_url.rstrip('/')
        self.session_id = None
        self.sse_thread = None
        self.sse_running = False
        self.event_callbacks = {}
        logger.info(f"MCP Toolkit initialized with server URL: {self.mcp_server_url}")
    
    def initialize_session(self) -> str:
        """Create a new session on the MCP server"""
        try:
            response = requests.post(f"{self.mcp_server_url}/api/session")
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("sessionId")
                logger.info(f"Session initialized with ID: {self.session_id}")
                return self.session_id
            else:
                logger.error(f"Failed to initialize session: {response.text}")
                raise Exception(f"Failed to initialize session: {response.status_code}")
        except Exception as e:
            logger.error(f"Error initializing session: {str(e)}")
            raise
    
    def reconnect_session(self, session_id: str) -> bool:
        """Reconnect to an existing session"""
        try:
            response = requests.get(f"{self.mcp_server_url}/api/session/{session_id}")
            if response.status_code == 200:
                self.session_id = session_id
                logger.info(f"Reconnected to session: {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found or expired")
                return False
        except Exception as e:
            logger.error(f"Error reconnecting to session: {str(e)}")
            return False
    
    def start_sse_listener(self, callback_function: Optional[Callable] = None):
        """Start listening for SSE events from the MCP server"""
        if not self.session_id:
            logger.error("Cannot start SSE listener: No active session")
            return False
        
        # Stop any existing SSE thread
        self.stop_sse_listener()
        
        # Start new SSE thread
        self.sse_running = True
        self.sse_thread = threading.Thread(target=self._sse_worker, args=(callback_function,))
        self.sse_thread.daemon = True
        self.sse_thread.start()
        logger.info(f"SSE listener started for session {self.session_id}")
        return True
    
    def _sse_worker(self, callback_function: Optional[Callable] = None):
        """Worker function for SSE listener thread"""
        try:
            url = f"{self.mcp_server_url}/api/sse/{self.session_id}"
            headers = {'Accept': 'text/event-stream'}
            
            logger.info(f"Connecting to SSE endpoint: {url}")
            response = requests.get(url, headers=headers, stream=True)
            
            if response.status_code != 200:
                logger.error(f"SSE connection failed: HTTP {response.status_code}")
                return
                
            client = sseclient.SSEClient(response)
            logger.info("SSE connection established")
            
            for event in client.events():
                if not self.sse_running:
                    break
                
                try:
                    event_data = json.loads(event.data)
                    event_type = event_data.get('type')
                    logger.debug(f"Received event: {event_type}")
                    
                    # Call the general callback if provided
                    if callback_function:
                        callback_function(event_data)
                    
                    # Call specific event callback if registered
                    if event_type in self.event_callbacks:
                        for cb in self.event_callbacks[event_type]:
                            cb(event_data)
                            
                except Exception as e:
                    logger.error(f"Error processing SSE event: {str(e)}")
        
        except Exception as e:
            if self.sse_running:  # Only log if we didn't stop intentionally
                logger.error(f"SSE connection error: {str(e)}")
                logger.info("Attempting to reconnect in 5 seconds...")
                time.sleep(5)
                if self.sse_running:
                    self._sse_worker(callback_function)
        
        logger.info("SSE listener thread stopped")
    
    def stop_sse_listener(self):
        """Stop the SSE listener thread"""
        if self.sse_thread and self.sse_running:
            self.sse_running = False
            if self.sse_thread.is_alive():
                self.sse_thread.join(timeout=2)
            logger.info("SSE listener stopped")
    
    def register_event_callback(self, event_type: str, callback_function: Callable):
        """Register a callback for a specific event type"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        
        self.event_callbacks[event_type].append(callback_function)
        return True
    
    # This method is used to execute tools on the MCP server via the ADK webhook
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict:
        """Execute a tool on the MCP server via the ADK webhook"""
        if not self.session_id:
            logger.error("Cannot execute tool: No active session")
            raise Exception("No active session")
        
        # Add session ID to parameters
        if parameters is None:
            parameters = {}
        
        parameters['mcp_session_id'] = self.session_id
        
        request_id = str(uuid.uuid4())
        request_data = {
            "session_id": str(uuid.uuid4()),  # ADK session ID (not MCP session ID)
            "tool_name": tool_name,
            "parameters": parameters,
            "request_id": request_id
        }
        
        try:
            logger.debug(f"Executing tool {tool_name} with parameters: {parameters}")
            response = requests.post(
                f"{self.mcp_server_url}/api/adk-webhook",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Tool execution result: {result}")
                return result
            else:
                error_message = f"Tool execution failed: HTTP {response.status_code} - {response.text}"
                logger.error(error_message)
                return {
                    "success": False,
                    "error": error_message
                }
        except Exception as e:
            logger.error(f"Error executing tool: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # File system operations
    def read_file(self, file_path: str, encoding: str = "utf-8") -> Dict:
        """Read a file using the MCP file system tool"""
        return self.execute_tool("file_system", {
            "operation": "read",
            "path": file_path,
            "encoding": encoding
        })
    
    def write_file(self, file_path: str, content: str, encoding: str = "utf-8") -> Dict:
        """Write a file using the MCP file system tool"""
        return self.execute_tool("file_system", {
            "operation": "write",
            "path": file_path,
            "content": content, 
            "encoding": encoding
        })
    
    def list_files(self, directory_path: str) -> Dict:
        """List files in a directory using the MCP file system tool"""
        return self.execute_tool("file_system", {
            "operation": "list",
            "path": directory_path
        })
    
    def delete_file(self, file_path: str) -> Dict:
        """Delete a file using the MCP file system tool"""
        return self.execute_tool("file_system", {
            "operation": "delete",
            "path": file_path
        })
    
    # API operations
    def call_api(self, endpoint: str, method: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Make an API call using the MCP API tool"""
        return self.execute_tool("api_call", {
            "endpoint": endpoint,
            "method": method,
            "data": data,
            "headers": headers
        })
    
    # Session data operations
    def get_session_data(self, key: Optional[str] = None) -> Dict:
        """Get session data from MCP server"""
        params = {"action": "get"}
        if key:
            params["key"] = key
        
        return self.execute_tool("session_data", params)
    
    def set_session_data(self, data: Dict) -> Dict:
        """Set session data on MCP server"""
        return self.execute_tool("session_data", {
            "action": "set",
            "data": data
        })
    
    # Weather tool
    def get_weather(self, location: str) -> Dict:
        """Get weather information using the MCP weather tool"""
        return self.execute_tool("weather", {
            "location": location
        })

# Singleton instance
_toolkit_instance = None

def get_toolkit() -> MCPToolkit:
    """Get a singleton instance of the MCP toolkit"""
    global _toolkit_instance
    if _toolkit_instance is None:
        _toolkit_instance = MCPToolkit()
        try:
            _toolkit_instance.initialize_session()
            
            # Start SSE listener
            def sse_callback(event_data):
                logger.debug(f"SSE event received: {event_data.get('type')}")
                
            _toolkit_instance.start_sse_listener(sse_callback)
        except Exception as e:
            logger.error(f"Failed to initialize MCP toolkit: {str(e)}")
            
    return _toolkit_instance