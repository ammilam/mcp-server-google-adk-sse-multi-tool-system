import logging
import os
from fastapi import FastAPI, HTTPException, Request, Depends, Response, Query
from fastapi.responses import RedirectResponse, JSONResponse
from google.adk.agents import Agent
from google.adk.server import get_fast_api_app
from dotenv import load_dotenv
import secrets
import json

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

# Import OAuth utilities if environment variables are set
try:
    from .oauth_utils import (
        is_oauth_enabled,
        create_oauth_flow,
        exchange_code_for_token,
        get_user_info,
        get_oauth_client_config
    )
    oauth_available = is_oauth_enabled()
    if oauth_available:
        logger.info("OAuth support is enabled")
    else:
        logger.info("OAuth support is available but not enabled (missing environment variables)")
except ImportError as e:
    logger.warning(f"OAuth support is not available: {e}")
    oauth_available = False

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
    return {
        "status": "healthy", 
        "session_id": toolkit.session_id,
        "oauth_enabled": oauth_available
    }

# Add OAuth routes if enabled
if oauth_available:
    # Store the state for CSRF protection
    oauth_states = {}
    
    @app.get("/oauth/login")
    async def oauth_login(request: Request):
        """Initiate OAuth login flow."""
        # Create a random state token for CSRF protection
        state = secrets.token_urlsafe(32)
        redirect_uri = str(request.url_for('oauth_callback'))
        
        # Create the OAuth flow
        flow = create_oauth_flow(redirect_uri=redirect_uri)
        if not flow:
            raise HTTPException(status_code=500, detail="Failed to initialize OAuth flow")
        
        # Store state temporarily
        oauth_states[state] = True
        
        # Generate the authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        
        # Redirect the user to the authorization URL
        return RedirectResponse(url=auth_url)
    
    @app.get("/oauth/callback")
    async def oauth_callback(
        request: Request,
        state: str = Query(...),
        code: str = Query(None),
        error: str = Query(None)
    ):
        """Handle OAuth callback."""
        # Verify state to prevent CSRF
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Clean up the state
        oauth_states.pop(state, None)
        
        # Check for errors
        if error:
            return JSONResponse(
                status_code=400,
                content={"error": error, "message": "Authentication failed"}
            )
        
        # Exchange code for token
        redirect_uri = str(request.url_for('oauth_callback'))
        token_info = exchange_code_for_token(code, redirect_uri)
        
        if not token_info:
            raise HTTPException(status_code=500, detail="Failed to exchange code for token")
        
        # Get user info
        user_info = get_user_info(token_info['access_token'])
        
        # Store token with MCP toolkit
        if user_info:
            toolkit.set_session_data({
                "oauth_user_info": user_info,
                "oauth_email": user_info.get("email"),
                "oauth_authenticated": True
            })
        
        # Return success response or redirect to the agent UI
        return RedirectResponse(url="/")
    
    @app.get("/oauth/status")
    async def oauth_status():
        """Check OAuth authentication status."""
        try:
            result = toolkit.get_session_data("oauth_authenticated")
            is_authenticated = result.get("data", False) if result.get("success") else False
            
            if is_authenticated:
                user_info_result = toolkit.get_session_data("oauth_user_info")
                user_info = user_info_result.get("data", {}) if user_info_result.get("success") else {}
                
                return {
                    "authenticated": True,
                    "user": user_info
                }
            else:
                return {"authenticated": False}
        except Exception as e:
            logger.error(f"Error checking OAuth status: {e}")
            return {"authenticated": False, "error": str(e)}
    
    @app.get("/oauth/logout")
    async def oauth_logout():
        """Log out the OAuth user."""
        try:
            # Clear OAuth data from session
            toolkit.set_session_data({
                "oauth_user_info": None,
                "oauth_email": None,
                "oauth_authenticated": False
            })
            return {"success": True, "message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return {"success": False, "error": str(e)}

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