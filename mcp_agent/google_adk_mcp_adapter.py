# google_adk_mcp_adapter.py
import requests
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
import sseclient
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GoogleADK-MCP-Adapter')

class MCPToolkit:
    """Adapter class to connect Google ADK agents with MCP Server"""
    
    def __init__(self, mcp_server_url: str = "http://localhost:8080"):
        """
        Initialize the MCP Toolkit
        
        Args:
            mcp_server_url: Base URL of the MCP server
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.session_id = None
        self.sse_thread = None
        self.sse_running = False
        self.event_callbacks = {}
    
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
    
    def start_sse_listener(self, callback_function=None):
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
        return True
    
    def _sse_worker(self, callback_function=None):
        """Worker function for SSE listener thread"""
        try:
            url = f"{self.mcp_server_url}/api/sse/{self.session_id}"
            headers = {'Accept': 'text/event-stream'}
            
            response = requests.get(url, headers=headers, stream=True)
            client = sseclient.SSEClient(response)
            
            for event in client.events():
                if not self.sse_running:
                    break
                
                try:
                    event_data = json.loads(event.data)
                    event_type = event_data.get('type')
                    
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
        
        logger.info("SSE listener thread stopped")
    
    def stop_sse_listener(self):
        """Stop the SSE listener thread"""
        if self.sse_thread and self.sse_running:
            self.sse_running = False
            self.sse_thread.join(timeout=2)
            logger.info("SSE listener stopped")
    
    def register_event_callback(self, event_type: str, callback_function):
        """Register a callback for a specific event type"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        
        self.event_callbacks[event_type].append(callback_function)
        return True
    
    def execute_tool(self, tool_name: str, parameters: Dict[Any, Any]) -> Dict:
        """Execute a tool on the MCP server"""
        if not self.session_id:
            logger.error("Cannot execute tool: No active session")
            raise Exception("No active session")
        
        # Add session ID to parameters
        if parameters is None:
            parameters = {}
        
        parameters['mcp_session_id'] = self.session_id
        
        request_data = {
            "session_id": str(uuid.uuid4()),  # ADK session ID (not MCP session ID)
            "tool_name": tool_name,
            "parameters": parameters,
            "request_id": str(uuid.uuid4())
        }
        
        try:
            response = requests.post(
                f"{self.mcp_server_url}/api/adk-webhook",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Tool execution failed: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP error {response.status_code}: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error executing tool: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # Convenience methods for different tools
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
    
    def call_api(self, endpoint: str, method: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Make an API call using the MCP API tool"""
        return self.execute_tool("api_call", {
            "endpoint": endpoint,
            "method": method,
            "data": data,
            "headers": headers
        })
    
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
    
    def get_weather(self, location: str) -> Dict:
        """Get weather information using the MCP weather tool"""
        return self.execute_tool("weather", {
            "location": location
        })


# Example configuration for Google ADK SseServerParams
def get_adk_tool_params(mcp_server_url: str = "http://localhost:8080"):
    """Generate the SseServerParams configuration for Google ADK"""
    return {
        "sse_server": {
            "url": f"{mcp_server_url}/api/adk-webhook",
            "auth_headers": {},
            "timeout_sec": 30
        }
    }