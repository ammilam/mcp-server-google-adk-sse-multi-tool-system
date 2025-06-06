import logging
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import secrets

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-agent-runner")

# Try to import ADK components for web UI
try:
    # Use the recommended import path for get_fast_api_app
    from google.adk.cli.fast_api import get_fast_api_app
    has_adk_web = True
    logger.info("Successfully imported ADK web interface components")
except ImportError:
    has_adk_web = False
    logger.warning("Could not import ADK web interface components - falling back to basic API")

# Check for OAuth support
try:
    from mcp_agent.oauth_utils import (
        is_oauth_enabled,
        create_oauth_flow,
        exchange_code_for_token,
        get_user_info
    )
    oauth_available = is_oauth_enabled()
    if oauth_available:
        logger.info("OAuth support is enabled")
    else:
        logger.info("OAuth support is available but not enabled (missing environment variables)")
except ImportError as e:
    logger.warning(f"OAuth support is not available: {e}")
    oauth_available = False

# Import our agent
try:
    # Import the agent package and the toolkit from the package
    from mcp_agent import root_agent  # Updated to use root_agent
    from mcp_agent.mcp_toolkit import get_toolkit
    toolkit_instance = get_toolkit()  # Ensures session is initialized
    logger.info(f"Agent and MCP Toolkit loaded successfully. Session ID: {toolkit_instance.session_id}")
    has_agent = True
except ImportError as e:
    logger.warning(f"Could not import agent, chat functionality will be disabled: {e}")
    has_agent = False

# Create FastAPI app - try to use ADK's helper if available
if has_adk_web:
    try:
        # AGENT_DIR should be the directory containing the 'mcp_agent' package
        AGENT_DIR = os.path.dirname(os.path.abspath(__file__))  # This is the project root

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
        return RedirectResponse(url="/docs")

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        from mcp_agent.mcp_toolkit import get_toolkit
        toolkit = get_toolkit()
        return {
            "status": "healthy", 
            "session_id": toolkit.session_id,
            "oauth_enabled": oauth_available
        }

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
            agent_response = root_agent.generate(request.message)  # Using root_agent now
            response_text = agent_response.text if hasattr(agent_response, 'text') else str(agent_response)
            logger.info(f"Agent response generated: {response_text}")
            return PromptResponse(response=response_text)
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            return PromptResponse(response=f"Error processing prompt: {str(e)}")

# Add OAuth routes if enabled
if oauth_available:
    # Store the state for CSRF protection
    oauth_states = {}
    
    @app.get("/oauth/login")
    async def oauth_login(request: Request):
        """Initiate OAuth login flow."""
        # Create a random state token for CSRF protection
        state = secrets.token_urlsafe(32)
        redirect_uri = str(request.url_for('oauth_callback').include_query_params())
        
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
        toolkit = get_toolkit()
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
            from mcp_agent.mcp_toolkit import get_toolkit
            toolkit = get_toolkit()
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
            from mcp_agent.mcp_toolkit import get_toolkit
            toolkit = get_toolkit()
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

# Add startup event to ensure MCP session is initialized if not already by agent import
@app.on_event("startup")
async def startup_event():
    """Ensure MCP session is initialized on startup."""
    try:
        from mcp_agent.mcp_toolkit import get_toolkit
        toolkit = get_toolkit()
        if not toolkit.session_id:
            logger.info("Toolkit session_id not found on startup, attempting to initialize.")
            toolkit.initialize_session()
            if toolkit.session_id:
                logger.info(f"MCP session re-initialized on startup: {toolkit.session_id}")
            else:
                logger.error("MCP session could not be initialized on startup.")
        else:
            logger.info(f"MCP session already initialized: {toolkit.session_id}")
    except Exception as e:
        logger.error(f"Error initializing MCP session on startup: {str(e)}")

@app.get("/custom-status")
async def custom_status():
    """Custom status endpoint"""
    from mcp_agent.mcp_toolkit import get_toolkit
    toolkit = get_toolkit()
    return {
        "custom": "endpoint", 
        "mcp_status": "connected" if toolkit.session_id else "disconnected", 
        "session_id": toolkit.session_id,
        "oauth_enabled": oauth_available
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))  # Use 8080 for containers
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)  # reload=True for local dev