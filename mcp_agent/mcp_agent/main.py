import logging
import os
from fastapi import FastAPI
from google.adk.agents import Agent
from google.adk.server import get_fast_api_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-agent-runner")


# Use relative imports as this main.py is part of the mcp_agent package
from .mcp_toolkit import get_toolkit
# Initialize the toolkit
toolkit = get_toolkit()

# Import the agent after toolkit is potentially initialized
from .agent import root_agent

# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up one level
# Example session DB URL (e.g., SQLite)
SESSION_DB_URL = "sqlite:///./sessions.db"
# Example allowed origins for CORS
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]

# Create FastAPI app using ADK's helper function
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_db_url=SESSION_DB_URL,
    allow_origins=ALLOWED_ORIGINS,
    web=True,  # Enable web interface
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "session_id": toolkit.session_id}

# Add startup event to ensure MCP session is initialized
@app.on_event("startup")
async def startup_event():
    """Ensure MCP session is initialized on startup."""
    try:
        toolkit = get_toolkit()
        if toolkit.session_id:
            logger.info(f"MCP session initialized: {toolkit.session_id}")
        else:
            logger.warning("MCP session could not be initialized")
    except Exception as e:
        logger.error(f"Error initializing MCP session: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("mcp_agent.main:app", host="0.0.0.0", port=port, reload=True)