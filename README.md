# MCP Server and Google ADK Multi-Tool System

## Adding a New Tool to MCP Server and Google ADK Agent System

This step-by-step guide will walk through the entire process of adding a new tool to the MCP server and making it available to a Google ADK agent. The guide below will use an image generation tool as our example.

### 1. System Overview

The system consists of two main components:

1. **MCP Server**: A TypeScript/Express server that provides tools for file operations, API calls, session data management, and weather information.
2. **Google ADK Agent**: A Python agent that connects to the MCP server and uses its tools through a webhook interface.

The communication flow is:
- Google ADK Agent receives user request
- Agent determines which tool to use
- Agent sends a request to MCP server's webhook endpoint
- MCP server processes the request and performs the operation
- MCP server returns result to the agent
- Agent formats the response for the user

### 2. Environment Setup

#### Prerequisites

- Node.js (v16+) for the MCP server
- Python (v3.9+) for the Google ADK agent
- Google ADK SDK installed (`pip install google-adk`)
- Google Project with Vertex AI enabled
- IAM permissions for the Google ADK agent to access Vertex AI

#### Setting Up the Environment

1. **Set up the MCP serve and the Google ADK Agentr**:
   ```bash
   # run this from the root directory of the project to setup the MCP server and the Google ADK agent
   ./scripts/setup.sh
   ```

2. **Configure environment variables**:
   - For MCP server, make sure .env contains:
     ```
     PORT=8080
     BASE_DIR=./data
     ```
   - For Google ADK agent, make sure .env contains:
     ```
     GOOGLE_CLOUD_PROJECT="your-google-project-id"
     GOOGLE_CLOUD_LOCATION="us-central1"
     GOOGLE_GENAI_USE_VERTEXAI="True"
     MCP_SERVER_URL=http://localhost:9000
     ```

3. **Run MCP Server**:
   ```bash
   # run this from the root directory of the project to start both the MCP server and the Google ADK agent
    ./scripts/run-mcp.sh
   ```

4. **Run Google ADK Agent**:
   ```bash
   # run this from the root directory of the project to start the Google ADK agent (in another terminal)
   adk web
   ```

5. **Open the web interface and select mcp_agent**:
   - Go to `http://localhost:8000` in browser
   - Select the `mcp_agent` from the dropdown
   - Chat with the agent to ensure it's working
   
6. **Test existing tools**:

### 3. Adding a New Tool to MCP Server

Let's add an image generation tool to the MCP server. We'll go through all required changes step-by-step.

#### Step 1: Create the Tool Implementation in MCP Server

First, let's add the core image generation functionality to the MCP server. Add this to the app.ts file in [mcp/app.ts](mcp/app.ts):

```typescript
// 1. Add new type for ImageGeneration operation
type ImageGenerationOptions = {
  prompt: string;
  width?: number; 
  height?: number;
  style?: string;
  format?: 'png' | 'jpeg' | 'webp';
  negativePrompt?: string;
};

// 2. Add the image generation tool implementation
const imageGenerationTool = async (options: ImageGenerationOptions): Promise<{success: boolean; data?: any; error?: string}> => {
  try {
    // Validate parameters
    if (!options.prompt) {
      return { success: false, error: 'Image prompt is required' };
    }
    
    // Set defaults for missing options
    const width = options.width || 512;
    const height = options.height || 512;
    const format = options.format || 'png';
    const style = options.style || 'photorealistic';
    
    console.log(`Generating image for prompt: "${options.prompt}" with style: ${style}, dimensions: ${width}x${height}`);
    
    // For this example, we'll just mock the image generation
    // In a real implementation, you would call an API like Stable Diffusion or DALL-E
    const mockImageData = {
      prompt: options.prompt,
      imageUrl: `https://example.com/generated_images/${Date.now()}.${format}`,
      width,
      height,
      style,
      format,
      generatedAt: new Date().toISOString()
    };
    
    // In a real implementation, you might store the image file
    // For mock purposes, write a metadata file
    const metadataPath = validatePath(`images/metadata_${Date.now()}.json`);
    const dir = path.dirname(metadataPath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(metadataPath, JSON.stringify(mockImageData, null, 2), 'utf-8');
    
    return {
      success: true,
      data: mockImageData
    };
  } catch (error: any) {
    console.error('Image generation error:', error);
    return {
      success: false, 
      error: error.message || 'Unknown error during image generation'
    };
  }
};
```

#### Step 2: Add Handler Function for Google ADK Webhook

Add this handler function to the MCP server to process requests from the Google ADK agent:

```typescript
// Add this to the handler functions section
async function handleImageGenerationTool(parameters: any, sessionId: string) {
  // Validate required parameters
  if (!parameters.prompt) {
    return { 
      success: false, 
      error: 'Missing required parameter: prompt' 
    };
  }
  
  // Create options object for the image generation tool
  const options: ImageGenerationOptions = {
    prompt: parameters.prompt,
    width: parameters.width || 512,
    height: parameters.height || 512,
    style: parameters.style || 'photorealistic',
    format: parameters.format || 'png',
    negativePrompt: parameters.negativePrompt
  };
  
  return await imageGenerationTool(options);
}
```

#### Step 3: Update the Switch Statement in ADK Webhook

Now, add a new case to the switch statement in the `/api/adk-webhook` route handler:

```typescript
// Find the switch statement in app.post('/api/adk-webhook', ...) 
switch (toolName) {
  case 'file_system':
    result = await handleFileSystemTool(parameters, mcpSessionId);
    break;
  case 'api_call':
    result = await handleApiTool(parameters, mcpSessionId);
    break;
  case 'session_data':
    result = await handleSessionDataTool(parameters, mcpSessionId);
    break;
  case 'weather':
    result = await handleWeatherTool(parameters, mcpSessionId);
    break;
  // Add the new case for image generation
  case 'image_generation':
    result = await handleImageGenerationTool(parameters, mcpSessionId);
    break;
  default:
    result = {
      success: false,
      error: `Unknown tool name: ${toolName}`
    };
}
```

#### Step 4: Add Endpoint for Direct Access

Add a dedicated endpoint for direct access to the image generation tool:

```typescript
// Add this route to the app
app.post('/api/session/:sessionId/image', async (req, res) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  const options: ImageGenerationOptions = req.body;

  if (!options.prompt) {
    return res.status(400).json({
      success: false,
      error: 'Image prompt is required'
    });
  }

  const result = await imageGenerationTool(options);

  if (result.success) {
    // Emit an event for SSE clients
    emitEvent(sessionId, 'image-generation', {
      imageUrl: result.data.imageUrl,
      prompt: options.prompt,
      timestamp: new Date().toISOString()
    });
    
    res.status(200).json(result);
  } else {
    res.status(400).json(result);
  }
});
```

#### Step 5: Update API Documentation

Add the new tool to the API documentation in the `/api/help` endpoint:

```typescript
// Find the endpoints array in the helpDocs object
endpoints: [
  // Add these new entries
  {
    path: "/api/session/{sessionId}/image",
    method: "POST",
    description: "Generate an image from a text prompt",
    parameters: [
      {
        name: "sessionId",
        in: "path",
        required: true,
        description: "Session identifier"
      }
    ],
    requestBodyExample: {
      prompt: "A beautiful sunset over mountains",
      width: 512,
      height: 512,
      style: "photorealistic",
      format: "png",
      negativePrompt: "blur, low quality"
    },
    responseExample: {
      success: true,
      data: {
        prompt: "A beautiful sunset over mountains",
        imageUrl: "https://example.com/generated_images/1717451623456.png",
        width: 512,
        height: 512,
        style: "photorealistic",
        format: "png",
        generatedAt: "2025-06-03T12:00:00.000Z"
      }
    },
    curlExample: `curl -X POST ${baseUrl}/api/session/{sessionId}/image \\
  -H "Content-Type: application/json" \\
  -d '{"prompt": "A beautiful sunset over mountains", "style": "photorealistic"}'`
  },
  // Add the Google ADK webhook documentation for image_generation tool
  {
    path: "/api/adk-webhook",
    method: "POST",
    description: "Webhook for Google ADK image generation",
    requestBodyExample: {
      session_id: "google-adk-session-123",
      tool_name: "image_generation",
      parameters: {
        prompt: "A beautiful sunset over mountains",
        width: 512,
        height: 512,
        style: "photorealistic"
      },
      request_id: "request-123"
    },
    responseExample: {
      success: true,
      data: {
        prompt: "A beautiful sunset over mountains",
        imageUrl: "https://example.com/generated_images/1717451623456.png",
        width: 512,
        height: 512,
        style: "photorealistic",
        format: "png",
        generatedAt: "2025-06-03T12:00:00.000Z"
      },
      mcp_session_id: "550e8400-e29b-41d4-a716-446655440000",
      request_id: "request-123"
    },
    notes: "This endpoint is used by the Google ADK agent to generate images."
  }
],
```

### 4. Adding Tool Support to Google ADK Agent

Now let's add the image generation tool to the Google ADK agent, which is found in [mcp_agent](mcp_agent).

#### Step 1: Add Method to MCPToolkit Class

First, add a new method to the [mcp_agent/mcp_toolkit.py](mcp_agent/mcp_toolkit.py) file to interact with the image generation tool:

```python
# Add this method to the MCPToolkit class in mcp_toolkit.py
def generate_image(self, prompt: str, width: int = 512, height: int = 512, 
                  style: str = "photorealistic", format: str = "png", 
                  negative_prompt: str = None) -> Dict:
    """Generate an image from a text prompt using the MCP server"""
    params = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "style": style,
        "format": format
    }
    
    if negative_prompt:
        params["negativePrompt"] = negative_prompt
        
    return self.execute_tool("image_generation", params)
```

#### Step 2: Add Tool Function to tools.py

Create a new tool function in [tools.py](mcp_agent/tools.py) that will be exposed to the ADK agent:

```python
# Add this to the tools.py file
def mcp_generate_image(prompt: str, style: str = "photorealistic", width: int = 512, height: int = 512) -> dict:
    """Generates an image from a text prompt.
    
    Args:
        prompt: Text description of the image to generate
        style: Style for the image (e.g., photorealistic, cartoon, sketch)
        width: Width of the output image in pixels
        height: Height of the output image in pixels
        
    Returns:
        dict: A dictionary with status ('success' or 'error') and either image info or error message
    """
    try:
        result = mcp_toolkit.generate_image(
            prompt=prompt, 
            style=style,
            width=width, 
            height=height
        )
        
        if result.get("success"):
            image_data = result.get("data", {})
            return {
                "status": "success",
                "image_url": image_data.get("imageUrl"),
                "message": f"Generated image for prompt: '{prompt}' in {style} style."
            }
        else:
            return {
                "status": "error",
                "error_message": result.get("error", "Unknown error generating image")
            }
    except Exception as e:
        logger.error(f"Error in mcp_generate_image: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Exception: {str(e)}"
        }
```

#### Step 3: Register the Tool with the Agent

Update [agent.py](mcp_agent/agent.py) file to include the new tool:

```python
# Add to the imports in agent.py
from .tools import (
    mcp_read_file, 
    mcp_write_file, 
    mcp_list_files, 
    mcp_delete_file,
    mcp_get_weather,
    mcp_call_api,
    mcp_store_data,
    mcp_store_number,
    mcp_store_boolean,
    mcp_retrieve_data,
    mcp_generate_image  # Add this import
)

# Update the agent definition
agent = Agent(
    name="mcp_agent",
    model="gemini-2.0-flash",
    description="Agent that can handle weather, time, and interact with a Model Control Protocol server",
    instruction="""I can help you with various tasks through my integration with the MCP server.
I can:
- Get current time in different cities
- Check weather conditions in locations
- Read, write, list, and delete files
- Make API calls to external services
- Store and retrieve data in a session (text, numbers, or boolean values)
- Generate images from text descriptions

When you ask me about files, I'll use the appropriate file operation tools.
When you ask me about weather, I'll look up the latest conditions.
When you want to store information for later, I'll use session storage.
When you ask me to create an image, I'll generate one based on your description.
""",
    tools=[
        # MCP file system tools
        mcp_read_file,
        mcp_write_file,
        mcp_list_files,
        mcp_delete_file,
        
        # MCP API tools
        mcp_call_api,
        mcp_get_weather,
        
        # MCP session tools
        mcp_store_data,
        mcp_store_number, 
        mcp_store_boolean, 
        mcp_retrieve_data,
        
        # New image generation tool
        mcp_generate_image  # Add this tool
    ]
)
```

### 5. Testing and Debugging

#### Testing the Tool Directly with cURL

Test the image generation endpoint directly using cURL:

```bash
# First create a session
export SESSION=$(curl -X POST http://localhost:8080/api/session | jq -r '.sessionId')

# Then call the image generation endpoint
curl -X POST http://localhost:8080/api/session/$SESSION/image \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains",
    "style": "photorealistic"
  }'
```

#### Testing through the ADK Webhook

Test the image generation through the ADK webhook:

```bash
curl -X POST http://localhost:8080/api/adk-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "tool_name": "image_generation",
    "parameters": {
      "prompt": "A beautiful sunset over mountains",
      "style": "photorealistic"
    },
    "request_id": "test-request-1"
  }'
```

#### Running the Agent and Testing the Tool

Run the agent and test the image generation tool with a prompt:

```bash
cd /mcp-server-google-adk-multi-tool-system
python -m mcp_agent.main
```

Then when the agent is running, try:

```
You: Generate an image of a cat playing piano
```

### 6. How Current Integrations Work

Let's examine how the existing integrations work in the system.

#### MCP Server Components

1. **Session Management**:
   - Each client gets a unique session ID
   - Sessions store user data and have a 30-minute expiration
   - Sessions are managed using a Map in memory

2. **Tool Implementation**:
   - Each tool (fileSystemTool, apiTool, etc.) is implemented as an async function
   - Tools handle validation, processing, and error handling
   - Tools return a standardized response object with `success`, `data`, and optional `error` fields

3. **Endpoints**:
   - Each tool has a dedicated endpoint (e.g., `/api/session/:sessionId/filesystem`)
   - A central webhook endpoint (`/api/adk-webhook`) handles requests from Google ADK
   - The webhook endpoint routes requests to appropriate handler functions based on `tool_name`

4. **Server-Sent Events (SSE)**:
   - The `/api/sse/:sessionId` endpoint enables real-time updates
   - The `emitEvent` function sends events to connected clients
   - Clients can listen for events through an EventSource connection

### Google ADK Agent Components

1. **MCPToolkit Class**:
   - Manages communication with the MCP server
   - Handles session creation and management
   - Provides methods for each tool operation
   - Maintains an SSE connection for real-time updates

2. **Tool Functions**:
   - Each tool function (mcp_read_file, mcp_get_weather, etc.) is a wrapper around MCPToolkit methods
   - Functions follow Google ADK format with proper documentation and type hints
   - Functions return standardized response objects with `status` and additional fields

3. **Agent Definition**:
   - The Agent class from Google ADK SDK defines agent capabilities
   - Agent registers tool functions and provides instructions
   - Agent handles NLU (Natural Language Understanding) for user inputs

4. **Main Runner**:
   - Initializes the agent and toolkit
   - Sets up event listeners
   - Manages the conversation loop
   - Handles errors and cleanup

### Data Flow Between Components

1. **User Request Flow**:
   - User sends text query to the agent
   - Agent processes the query and determines the appropriate tool
   - Agent calls the tool function with extracted parameters
   - Tool function calls MCPToolkit method
   - MCPToolkit sends request to MCP server webhook
   - MCP server processes request and returns result
   - Result flows back through the same chain in reverse

2. **Server-Sent Events Flow**:
   - MCP server processes an operation
   - Server emits event with `emitEvent`
   - SSE connection transmits event to client
   - MCPToolkit receives event in `_sse_worker` thread
   - Event callback processes the event

## Summary

Adding a new tool to the MCP server and Google ADK agent involves these key steps:

1. **MCP Server**:
   - Create the tool implementation function
   - Add a handler function for the webhook
   - Update the webhook switch statement
   - Add a dedicated endpoint if needed
   - Update API documentation

2. **Google ADK Agent**:
   - Add a method to the MCPToolkit class
   - Create a tool function in tools.py
   - Register the tool with the agent
   - Update agent instructions

By following this guide, you can easily extend the MCP server and Google ADK agent with new tools and capabilities. The modular design makes it straightforward to add new features while maintaining a consistent interface and error handling approach.