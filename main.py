import logging
import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-agent-runner")

# No longer need sys.path.insert(0, "/app") if main.py is at the root
# and mcp_agent is in the same directory or PYTHONPATH is set correctly in Docker.

# Try to import ADK components for web UI
try:
    # Use the recommended import path for get_fast_api_app
    from google.adk.cli.fast_api import get_fast_api_app
    has_adk_web = True
    logger.info("Successfully imported ADK web interface components")
except ImportError:
    # Fallback if ADK web components are not found (less likely with google-adk in requirements)
    has_adk_web = False
    logger.warning("Could not import ADK web interface components - falling back to basic API")

# Import our agent
try:
    from mcp_agent.mcp_agent import agent
    has_agent = True
    # Initialize the toolkit by calling get_toolkit() which is done in agent.py
    from mcp_agent.mcp_toolkit import get_toolkit as init_toolkit
    toolkit_instance = init_toolkit() # Ensures session is initialized
    logger.info(f"Agent and MCP Toolkit loaded successfully. Session ID: {toolkit_instance.session_id}")
except ImportError:
    logger.warning("Could not import agent, chat functionality will be disabled")
    has_agent = False

# Initialize the toolkit
from mcp_agent.mcp_toolkit import get_toolkit
toolkit = get_toolkit()
logger.info(f"MCP Toolkit (re)confirmed with server URL: {toolkit.mcp_server_url}, Session ID: {toolkit.session_id}")

# Create FastAPI app - try to use ADK's helper if available
if has_adk_web:
    try:
        # AGENT_DIR should be the directory containing the 'mcp_agent' package
        # If main.py is at the root, this is the current directory.
        AGENT_DIR = os.path.dirname(os.path.abspath(__file__)) # This is now the project root

        SESSION_DB_URL = os.environ.get("SESSION_DB_URL", "sqlite:///./sessions.db")
        # Example allowed origins for CORS
        ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost,http://localhost:8080,*").split(',')

        # Call ADK's function to get the FastAPI app with web interface
        app = get_fast_api_app(
            agents_dir=AGENT_DIR,
            session_db_url=SESSION_DB_URL,
            allow_origins=ALLOWED_ORIGINS,
            web=True
        )
        logger.info("Using ADK's FastAPI app with web interface")
    except Exception as e:
        logger.error(f"Error setting up ADK's FastAPI app: {str(e)}")
        # Fall back to basic FastAPI app
        app = FastAPI(title="MCP Agent API")
        has_adk_web = False
else:
    # Create a basic FastAPI app
    app = FastAPI(title="MCP Agent API")

# Add CORS middleware if not already added by ADK
if not has_adk_web:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Define basic API routes if not using ADK's web interface
if not has_adk_web:
    @app.get("/")
    async def root():
        """Root endpoint - redirect to docs"""
        # If ADK web is true, it serves its own UI at /
        # Otherwise, redirect to FastAPI docs or a custom health/status
        return RedirectResponse(url="/docs" if not has_adk_web else "/")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "session_id": toolkit.session_id}

    # Define Pydantic models for chat
    from pydantic import BaseModel
    
    class PromptRequest(BaseModel):
        message: str
    
    class PromptResponse(BaseModel):
        response: str
    
    @app.post("/chat", response_model=PromptResponse)
    async def send_prompt(request: PromptRequest):
        """Send a prompt to the agent and get a response"""
        if not has_agent:
            return PromptResponse(response="Agent functionality is not available.")

        try:
            logger.info(f"Received prompt: {request.message}")
            # Use the agent's generate method
            agent_response = agent.generate(request.message)
            response_text = agent_response.text if hasattr(agent_response, 'text') else str(agent_response)
            logger.info(f"Agent response generated: {response_text}")
            return PromptResponse(response=response_text)
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            return PromptResponse(response=f"Error processing prompt: {str(e)}")

# Add startup event to ensure MCP session is initialized if not already by agent import
@app.on_event("startup")
async def startup_event():
    """Ensure MCP session is initialized on startup."""
    if not toolkit.session_id:
        logger.warning("Toolkit session_id not found on startup, attempting to initialize.")
        try:
            toolkit.initialize_session() # This might be redundant if agent import already did it
            if toolkit.session_id:
                logger.info(f"MCP session re-initialized on startup: {toolkit.session_id}")
            else:
                logger.error("MCP session could not be initialized on startup.")
        except Exception as e:
            logger.error(f"Error initializing MCP session on startup: {str(e)}")

@app.get("/custom-status")
async def custom_status():
    """Custom status endpoint"""
    return {"custom": "endpoint", "mcp_status": "connected" if toolkit.session_id else "disconnected", "session_id": toolkit.session_id}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080")) # Default to 8080 for GKE/Cloud Run
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) # reload=True for local dev