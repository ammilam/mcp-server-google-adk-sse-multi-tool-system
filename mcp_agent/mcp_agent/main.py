import os
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-agent-runner")

# Initialize MCP toolkit early
try:
    from mcp_agent.mcp_toolkit import get_toolkit
    toolkit = get_toolkit()
    logger.info(f"MCP toolkit initialized with session ID: {toolkit.session_id}")
except Exception as e:
    logger.error(f"Failed to initialize MCP toolkit: {e}")
    toolkit = None

# Try to import ADK components for web UI
try:
    # For Google ADK deployment
    from google.adk.cli.fast_api import get_fast_api_app
    has_adk_web = True
    logger.info("Successfully imported ADK web interface components")
    
    # Import the agent after toolkit initialization
    try:
        from mcp_agent import root_agent
        has_agent = True
        logger.info("Agent imported successfully")
    except ImportError as e:
        logger.warning(f"Could not import agent: {e}")
        has_agent = False
        
except ImportError:
    has_adk_web = False
    logger.warning("Could not import ADK web interface components - falling back to basic API")

# Create FastAPI app - try to use ADK's helper if available
if has_adk_web:
    try:
        # AGENT_DIR should point to the directory containing the mcp_agent package
        AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  
        SESSION_DB_URL = os.environ.get("SESSION_DB_URL", "sqlite:///./sessions.db")
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
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        app = FastAPI(title="MCP Agent API")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        has_adk_web = False
else:
    # Create a basic FastAPI app for GKE deployment
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(title="MCP Agent API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add startup event to ensure MCP session is initialized
@app.on_event("startup")
async def startup_event():
    """Ensure MCP session is initialized on startup."""
    try:
        from mcp_agent.mcp_toolkit import get_toolkit
        toolkit = get_toolkit()
        if toolkit.session_id:
            logger.info(f"MCP session initialized: {toolkit.session_id}")
        else:
            logger.warning("MCP session could not be initialized")
    except Exception as e:
        logger.error(f"Error initializing MCP session: {str(e)}")

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from mcp_agent.mcp_toolkit import get_toolkit
    toolkit = get_toolkit()
    return {
        "status": "healthy", 
        "session_id": toolkit.session_id,
        "deployment_type": "google-adk" if has_adk_web else "standalone",
        "agent_available": has_agent
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)