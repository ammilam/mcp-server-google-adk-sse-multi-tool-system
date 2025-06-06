import os
import json
import logging
from typing import Dict, Optional, Tuple, Any
import requests
from google.cloud import secretmanager
from google.oauth2 import credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import google_crc32c

# Configure logging
logger = logging.getLogger("oauth-utils")

def is_oauth_enabled() -> bool:
    """Check if OAuth is enabled based on environment variables."""
    required_vars = ["GOOGLE_CLOUD_PROJECT", "OAUTH_SECRET_ID"]
    return all(os.environ.get(var) for var in required_vars)

def get_oauth_client_config() -> Optional[Dict[str, Any]]:
    """Retrieve OAuth client configuration from Secret Manager."""
    if not is_oauth_enabled():
        logger.info("OAuth is not enabled (missing required environment variables)")
        return None
    
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        secret_id = os.environ.get("OAUTH_SECRET_ID")
        
        # Create the Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the resource name of the latest secret version
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        
        # Access the secret version
        response = client.access_secret_version(request={"name": name})
        
        # Decode the payload
        payload = response.payload.data.decode("UTF-8")
        
        # Parse and return the JSON configuration
        return json.loads(payload)
    except Exception as e:
        logger.error(f"Error retrieving OAuth client config: {e}")
        return None

def create_oauth_flow(redirect_uri: Optional[str] = None, scopes: Optional[list] = None) -> Optional[Flow]:
    """Create OAuth flow object for authorization."""
    try:
        client_config = get_oauth_client_config()
        if not client_config:
            return None
        
        # Use provided scopes or default to common scopes
        if scopes is None:
            scopes = [
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'openid'
            ]
        
        # Create flow instance using client config and scopes
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=redirect_uri or client_config['web']['redirect_uris'][0]
        )
        
        return flow
    except Exception as e:
        logger.error(f"Error creating OAuth flow: {e}")
        return None

def exchange_code_for_token(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for tokens."""
    try:
        flow = create_oauth_flow(redirect_uri=redirect_uri)
        if not flow:
            return None
            
        # Exchange code for tokens
        flow.fetch_token(code=code)
        
        # Get credentials and token information
        creds = flow.credentials
        
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
            "scopes": creds.scopes
        }
    except Exception as e:
        logger.error(f"Error exchanging code for token: {e}")
        return None

def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user information using the access token."""
    try:
        # Call the userinfo endpoint
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error fetching user info: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception fetching user info: {e}")
        return None

def store_oauth_client_secret(client_config: Dict[str, Any]) -> bool:
    """Store OAuth client config in Secret Manager."""
    if not os.environ.get("GOOGLE_CLOUD_PROJECT") or not os.environ.get("OAUTH_SECRET_ID"):
        logger.error("Missing required environment variables for Secret Manager")
        return False
        
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        secret_id = os.environ.get("OAUTH_SECRET_ID")
        
        # Initialize the Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Check if secret exists
        try:
            secret_path = f"projects/{project_id}/secrets/{secret_id}"
            client.get_secret(request={"name": secret_path})
            secret_exists = True
        except Exception:
            secret_exists = False
        
        # Create secret if it doesn't exist
        if not secret_exists:
            parent = f"projects/{project_id}"
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {
                        "labels": {"type": "oauth_client"},
                        "replication": {"automatic": {}}
                    }
                }
            )
        
        # Prepare the secret payload
        payload = json.dumps(client_config).encode("UTF-8")
        
        # Calculate CRC32C checksum
        crc32c = google_crc32c.Checksum()
        crc32c.update(payload)
        
        # Add the secret version
        secret_path = f"projects/{project_id}/secrets/{secret_id}"
        client.add_secret_version(
            request={
                "parent": secret_path,
                "payload": {
                    "data": payload,
                    "data_crc32c": int(crc32c.hexdigest(), 16)
                }
            }
        )
        
        logger.info(f"OAuth client secret stored successfully with ID: {secret_id}")
        return True
    except Exception as e:
        logger.error(f"Error storing OAuth client config: {e}")
        return False