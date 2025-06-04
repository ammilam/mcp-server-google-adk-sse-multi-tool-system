import express from 'express';
import fs from 'fs/promises';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import morgan from 'morgan';
import cors from 'cors';
import { createHash } from 'crypto';
import { EventEmitter } from 'events';

// Define types for our application
type Session = {
  id: string;
  created: Date;
  lastAccessed: Date;
  data: Record<string, any>;
};

type FileOperation = {
  operation: 'read' | 'write' | 'list' | 'delete';
  path: string;
  content?: string;
  encoding?: BufferEncoding;
};

type ApiOperation = {
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  data?: any;
  headers?: Record<string, string>;
  access_token?: string; // Optional access token for authenticated APIs
  content_type?: string; // Optional content type for the request, default is application/json
};

// Create Express app
const app: express.Application = express();
const PORT = process.env.PORT || 9000;
const MAX_EVENT_LISTENERS: number = process.env.MAX_EVENT_LISTENERS ? parseInt(process.env.MAX_EVENT_LISTENERS) : 100;

// Create a global event emitter for SSE
const eventEmitter = new EventEmitter();
eventEmitter.setMaxListeners(MAX_EVENT_LISTENERS);

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(morgan('dev'));
app.use(cors());

// Session management
const sessions = new Map<string, Session>();


// Session cleanup - remove sessions older than 30 minutes
setInterval(() => {
  const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);
  sessions.forEach((session, id) => {
    if (session.lastAccessed < thirtyMinutesAgo) {
      sessions.delete(id);
      console.log(`Session ${id} expired and removed`);
    }
  });
}, 60 * 1000); // Check every minute

// Function to get session by ID and update last accessed time
const getSessionAndUpdate = (sessionId: string): Session | null => {
  if (!sessions.has(sessionId)) return null;

  const session = sessions.get(sessionId)!;
  session.lastAccessed = new Date();
  sessions.set(sessionId, session);
  return session;
};

// Function to validate and normalize file paths
const validatePath = (filePath: string): string => {
  // Resolve path and prevent directory traversal
  const normalizedPath = path.normalize(filePath).replace(/^(\.\.[\/\\])+/, '');
  return path.resolve(process.env.BASE_DIR || './data', normalizedPath);
};

// Weather tool implementation
const getWeatherTool = async (location: string): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    // Mock weather data for demonstration purposes
    const mockWeatherData = {
      location,
      temperature: '22°C',
      condition: 'Sunny',
      humidity: '45%',
      windSpeed: '10 km/h',
      timestamp: new Date().toISOString()
    };

    return { success: true, data: mockWeatherData };
  } catch (error: any) {
    console.error(`Weather API error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown weather API error'
    };
  }
};

// File system tool implementation that handles basic file operations
const fileSystemTool = async (operation: FileOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    const safePath = validatePath(operation.path);

    switch (operation.operation) {
      case 'read':
        const content = await fs.readFile(safePath, operation.encoding || 'utf-8');
        return { success: true, data: content };

      case 'write':
        if (!operation.content) {
          return { success: false, error: 'No content provided for write operation' };
        }

        // Ensure directory exists
        const dir = path.dirname(safePath);
        await fs.mkdir(dir, { recursive: true });

        await fs.writeFile(safePath, operation.content, operation.encoding || 'utf-8');
        return { success: true };

      case 'list':
        const stats = await fs.stat(safePath);
        if (stats.isFile()) {
          return { success: true, data: [path.basename(safePath)] };
        } else {
          const files = await fs.readdir(safePath);
          return { success: true, data: files };
        }

      case 'delete':
        await fs.unlink(safePath);
        return { success: true };

      default:
        return { success: false, error: 'Unsupported file operation' };
    }
  } catch (error: any) {
    console.error(`File system error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown file system error'
    };
  }
};

// API tool implementation that makes HTTP requests
const apiTool = async (operation: ApiOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    const { endpoint, method, data, headers, access_token, content_type } = operation;
  
    if (!endpoint || !method) {
      return { success: false, error: 'Endpoint and method are required' };
    }

    // Ensure the URL has a protocol
    let url = endpoint;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'http://' + url;
    }

    console.log(`Making API call to ${url} with method ${method}`);
    
    // Create request config
    const requestConfig: any = {
      method,
      url,
      headers: {
        'Content-Type': content_type || 'application/json',
        ...(headers || {}),
        ...(access_token ? { Authorization: `Bearer ${access_token}` } : {})
      }
    };

    // Only add data if it's provided and not for GET requests
    if (data && method.toUpperCase() !== 'GET') {
      requestConfig.data = data;
    }

    const response = await axios(requestConfig);

    // Check if the response has any data before returning
    return {
      success: true,
      data: response.data || null
    };
  } catch (error: any) {
    console.error(`API error:`, error.message || error);
    return {
      success: false,
      error: error.message || 'Unknown API error'
    };
  }
};

// Routes
// Initialize a new session
app.post('/api/session', (req: any, res: any) => {
  const sessionId = uuidv4();
  const session: Session = {
    id: sessionId,
    created: new Date(),
    lastAccessed: new Date(),
    data: {}
  };

  sessions.set(sessionId, session);

  res.status(200).json({
    success: true,
    sessionId,
    message: 'Session created successfully'
  });
});

// Get all session data
app.get('/api/session/:sessionId/data', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Return all session data
  res.status(200).json({
    success: true,
    data: session.data
  });
});

// Get session info
app.get('/api/session/:sessionId', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  res.status(200).json({
    success: true,
    session: {
      id: session.id,
      created: session.created,
      lastAccessed: session.lastAccessed,
      dataKeys: Object.keys(session.data)
    }
  });
});

// Set session data
app.post('/api/session/:sessionId/data', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Check if the body is an object and not null
  if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) {
    return res.status(400).json({
      success: false,
      error: 'Request body must be a JSON object'
    });
  }

  // Store each key-value pair from the request body into the session data
  Object.entries(req.body).forEach(([key, value]) => {
    session.data[key] = value;
  });

  res.status(200).json({
    success: true,
    message: `Data stored with ${Object.keys(req.body).length} key(s)`,
    keys: Object.keys(req.body)
  });
});

// Get session data for a specific key
app.get('/api/session/:sessionId/data/:key', (req: any, res: any) => {
  const { sessionId, key } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  if (!(key in session.data)) {
    return res.status(404).json({
      success: false,
      error: `Key '${key}' not found in session data`
    });
  }

  res.status(200).json({
    success: true,
    key,
    value: session.data[key]
  });
});

// File system operations
app.post('/api/session/:sessionId/filesystem', async (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  const operation: FileOperation = req.body;

  if (!operation.operation || !operation.path) {
    return res.status(400).json({
      success: false,
      error: 'Invalid file operation request'
    });
  }

  const result = await fileSystemTool(operation);

  if (result.success) {
    res.status(200).json(result);
  } else {
    res.status(400).json(result);
  }
});

// API operations, this endpoint allows making API calls using the MCP server
app.post('/api/session/:sessionId/api', async (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  const operation: ApiOperation = req.body;

  if (!operation.endpoint || !operation.method) {
    return res.status(400).json({
      success: false,
      error: 'Invalid API operation request'
    });
  }

  const result = await apiTool(operation); // Call the API tool with the operation

  if (result.success) {
    res.status(200).json(result);
  } else {
    res.status(400).json(result);
  }
});

// Health check endpoint
app.get('/health', (req: any, res: any) => {
  res.status(200).json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    sessions: sessions.size
  });
});

// Add an SSE endpoint to your MCP server
app.get('/api/sse/:sessionId', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Configure SSE
  res.setHeader('Content-Type', 'text/event-stream'); // Set the content type for SSE, used by browsers to handle server-sent events
  res.setHeader('Cache-Control', 'no-cache'); // Disable caching
  res.setHeader('Connection', 'keep-alive'); // Keep the connection open

  // Send initial connection established message
  res.write(`data: ${JSON.stringify({ type: 'connection', status: 'established', sessionId })}\n\n`);

  // Create a listener function for this client
  const listener = (eventData: any) => {
    if (eventData.sessionId === sessionId) {
      res.write(`data: ${JSON.stringify(eventData)}\n\n`);
    }
  };

  // Register listener
  eventEmitter.on('mcp-event', listener);

  // Handle client disconnect
  req.on('close', () => {
    eventEmitter.removeListener('mcp-event', listener);
    console.log(`SSE connection closed for session ${sessionId}`);
  });
});

// Function to emit events to SSE clients
function emitEvent(sessionId: string, eventType: string, data: any) {
  eventEmitter.emit('mcp-event', {
    sessionId,
    type: eventType,
    data,
    timestamp: new Date().toISOString()
  });
}

app.post('/api/adk-webhook', express.json({ limit: '50mb' }), async (req: any, res: any) => {
  try {
    console.log('Received webhook request from Google ADK');

    // Extract the request data from the Google ADK agent
    const {
      session_id: googleSessionId,
      tool_name: toolName,
      parameters,
      request_id: requestId
    } = req.body;

    // If no session ID is provided, create a new one
    let mcpSessionId: string;
    if (parameters && parameters.mcp_session_id) {
      // Use the session ID provided in parameters
      mcpSessionId = parameters.mcp_session_id;

      // Verify the session exists
      const session = getSessionAndUpdate(mcpSessionId);
      if (!session) {
        // Create a new session
        const sessionResponse = await createNewSession();
        mcpSessionId = sessionResponse.sessionId;
      }
    } else {
      // Create a new session for this conversation
      const sessionResponse = await createNewSession();
      mcpSessionId = sessionResponse.sessionId;
    }

    // Process based on tool name
    // NOTE: IF ADDING A NEW TOOL, THERE MUST BE A CASE HERE
    let result;
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
        // Add more cases here for additional tools
      default:
        result = {
          success: false,
          error: `Unknown tool name: ${toolName}`
        };
    }

    // Emit event for SSE clients
    emitEvent(mcpSessionId, 'tool-execution', {
      toolName,
      requestId,
      result,
      timestamp: new Date().toISOString()
    });

    // Return response with the session ID and result
    return res.status(200).json({
      success: result.success,
      data: result.data,
      error: result.error,
      mcp_session_id: mcpSessionId,
      request_id: requestId
    });
  } catch (error: any) {
    console.error('Error processing ADK webhook:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Unknown error processing the request'
    });
  }
});

// Helper function to create a new session
async function createNewSession() {
  const sessionId = uuidv4();
  const session: Session = {
    id: sessionId,
    created: new Date(),
    lastAccessed: new Date(),
    data: {}
  };

  sessions.set(sessionId, session);

  return {
    sessionId,
    message: 'Session created successfully'
  };
}

// Tool handler functions
async function handleFileSystemTool(parameters: any, sessionId: string) {
  if (!parameters.operation || !parameters.path) {
    return {
      success: false,
      error: 'Invalid file operation request. Required parameters: operation, path'
    };
  }

  const operation: FileOperation = {
    operation: parameters.operation,
    path: parameters.path,
    content: parameters.content,
    encoding: parameters.encoding || 'utf-8'
  };

  return await fileSystemTool(operation);
}

async function handleApiTool(parameters: any, sessionId: string) {
  if (!parameters.endpoint || !parameters.method) {
    return {
      success: false,
      error: 'Invalid API operation request. Required parameters: endpoint, method'
    };
  }

  // Log the API call for debugging
  console.log(`Processing API request: ${parameters.method} ${parameters.endpoint}`);
  
  const operation: ApiOperation = {
    endpoint: parameters.endpoint,
    method: parameters.method.toUpperCase(), // Normalize method to uppercase
    data: parameters.data || null,
    headers: parameters.headers || {},
    access_token: parameters.access_token || null,
    content_type: parameters.content_type || 'application/json'
  };

  return await apiTool(operation);
}

async function handleSessionDataTool(parameters: any, sessionId: string) {
  const session = getSessionAndUpdate(sessionId);
  if (!session) {
    return {
      success: false,
      error: 'Session not found'
    };
  }

  // Handle data operations
  if (parameters.action === 'get') {
    if (parameters.key) {
      if (parameters.key in session.data) {
        return {
          success: true,
          data: session.data[parameters.key]
        };
      } else {
        return {
          success: false,
          error: `Key '${parameters.key}' not found in session data`
        };
      }
    } else {
      return {
        success: true,
        data: session.data
      };
    }
  } else if (parameters.action === 'set') {
    if (!parameters.data || typeof parameters.data !== 'object') {
      return {
        success: false,
        error: 'Missing or invalid data property for set action'
      };
    }

    // Store each key from the data object
    Object.entries(parameters.data).forEach(([key, value]) => {
      session.data[key] = value;
    });

    return {
      success: true,
      data: {
        message: `Successfully stored ${Object.keys(parameters.data).length} items in session`,
        keys: Object.keys(parameters.data)
      }
    };
  } else {
    return {
      success: false,
      error: `Invalid action: ${parameters.action}. Supported actions: get, set`
    };
  }
}

async function handleWeatherTool(parameters: any, sessionId: string) {
  if (!parameters.location) {
    return {
      success: false,
      error: 'Missing required parameter: location'
    };
  }

  return await getWeatherTool(parameters.location);
}

// API Help documentation endpoint
app.get('/api/help', (req: any, res: any) => {
  const baseUrl = `${req.protocol}://${req.get('host')}`;

  const helpDocs = {
    title: "MCP Server API Documentation",
    description: "This API provides tools for file operations, API calls, and stateful session management.",
    version: "1.0.0",
    baseUrl: baseUrl,

    endpoints: [
      {
        path: "/api/session",
        method: "POST",
        description: "Initialize a new session to use across requests",
        requestBody: "None",
        responseExample: {
          success: true,
          sessionId: "550e8400-e29b-41d4-a716-446655440000",
          message: "Session created successfully"
        },
        curlExample: `curl -X POST ${baseUrl}/api/session`
      },
      {
        path: "/api/session/{sessionId}",
        method: "GET",
        description: "Get information about an existing session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        responseExample: {
          success: true,
          session: {
            id: "550e8400-e29b-41d4-a716-446655440000",
            created: "2025-06-02T12:00:00.000Z",
            lastAccessed: "2025-06-02T12:05:00.000Z",
            dataKeys: ["username", "preferences"]
          }
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}`
      },
      {
        path: "/api/session/{sessionId}/data",
        method: "POST",
        description: "Store data in the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExample: {
          string: "test",
          number: 12,
          nested: { key: "value" }
        },
        responseExample: {
          success: true,
          message: "Data stored with 3 key(s)",
          keys: ["string", "number", "nested"]
        },
        curlExample: `curl -X POST ${baseUrl}/api/session/{sessionId}/data \\
    -H "Content-Type: application/json" \\
    -d '{"string": "test", "number": 12, "nested": {"key": "value"}}'`
      },
      {
        path: "/api/session/{sessionId}/data",
        method: "GET",
        description: "Get all data stored in the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        responseExample: {
          success: true,
          data: {
            string: "test",
            number: 12,
            nested: { key: "value" }
          }
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}/data`
      },
      {
        path: "/api/session/{sessionId}/data/{key}",
        method: "GET",
        description: "Get a specific data key from the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          },
          {
            name: "key",
            in: "path",
            required: true,
            description: "Data key to retrieve"
          }
        ],
        responseExample: {
          success: true,
          key: "string",
          value: "test"
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}/data/string`
      },
      {
        path: "/api/session/{sessionId}/filesystem",
        method: "POST",
        description: "Perform file system operations",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExamples: {
          read: {
            operation: "read",
            path: "example.txt"
          },
          write: {
            operation: "write",
            path: "example.txt",
            content: "File content goes here"
          },
          list: {
            operation: "list",
            path: "directory"
          },
          delete: {
            operation: "delete",
            path: "example.txt"
          }
        },
        responseExamples: {
          read: {
            success: true,
            data: "File content goes here"
          },
          write: {
            success: true
          },
          list: {
            success: true,
            data: ["file1.txt", "file2.txt", "subdirectory"]
          },
          delete: {
            success: true
          }
        },
        curlExamples: {
          read: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "read", "path": "example.txt"}'`,
          write: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "write", "path": "example.txt", "content": "File content goes here"}'`,
          list: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "list", "path": "directory"}'`,
          delete: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "delete", "path": "example.txt"}'`
        }
      },
      {
        path: "/api/session/{sessionId}/api",
        method: "POST",
        description: "Make API calls using the MCP server",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExamples: {
          hello: {
            endpoint: "hello",
            method: "GET"
          },
          echo: {
            endpoint: "echo",
            method: "POST",
            data: {
              message: "Hello, world!"
            }
          },
          weather: {
            endpoint: "weather",
            method: "GET",
            data: {
              location: "New York"
            }
          }
        },
        responseExamples: {
          hello: {
            success: true,
            data: {
              message: "Hello, world!",
              timestamp: "2025-06-02T12:00:00.000Z"
            }
          },
          echo: {
            success: true,
            data: {
              message: "Hello, world!"
            }
          }
        },
        curlExamples: {
          hello: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "hello", "method": "GET"}'`,
          echo: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "echo", "method": "POST", "data": {"message": "Hello, world!"}}'`
        }
      },
      {
        path: "/health",
        method: "GET",
        description: "Check the health status of the MCP server",
        responseExample: {
          status: "ok",
          timestamp: "2025-06-02T12:00:00.000Z",
          uptime: 3600,
          sessions: 5
        },
        curlExample: `curl -X GET ${baseUrl}/health`
      }
    ],

    // Common workflow examples
    workflows: [
      {
        name: "Complete Session Workflow",
        description: "Initialize a session, store data, and use tools",
        steps: [
          {
            description: "1. Create a new session",
            command: `curl -X POST ${baseUrl}/api/session`
          },
          {
            description: "2. Store your session ID in a variable",
            command: `export SESSION=550e8400-e29b-41d4-a716-446655440000  # Replace with your actual session ID`
          },
          {
            description: "3. Store data in your session",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/data \\
    -H "Content-Type: application/json" \\
    -d '{"username": "john_doe", "preferences": {"theme": "dark"}}'`
          },
          {
            description: "4. Retrieve all session data",
            command: `curl -X GET ${baseUrl}/api/session/$SESSION/data`
          },
          {
            description: "5. Write a file using the filesystem tool",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "write", "path": "notes.txt", "content": "Important information"}'`
          },
          {
            description: "6. Make an API call",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "hello", "method": "GET"}'`
          }
        ]
      }
    ],

    // Format guide
    requestFormats: {
      fileSystem: {
        operation: "Type of operation (read, write, list, or delete)",
        path: "Path to the file or directory",
        content: "File content for write operations",
        encoding: "Optional encoding for file operations (default: utf-8)"
      },
      api: {
        endpoint: "API endpoint to call",
        method: "HTTP method (GET, POST, PUT, DELETE)",
        data: "Optional data to send with the request",
        headers: "Optional headers for the request"
      }
    }
  };

  // Format help documentation as HTML if requested
  const acceptHeader = req.get('Accept');
  if (acceptHeader && acceptHeader.includes('text/html')) {
    const html = generateHtmlDocs(helpDocs);
    res.setHeader('Content-Type', 'text/html');
    res.send(html);
    return;
  }

  // Default to JSON response
  res.status(200).json(helpDocs);
});

// Helper function to generate HTML documentation
function generateHtmlDocs(docs: any): string {
  return `
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${docs.title}</title>
    <style>
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
      }
      h1, h2, h3 {
        color: #2c3e50;
      }
      .endpoint {
        background-color: #f8f9fa;
        border-left: 4px solid #3498db;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 4px;
      }
      .method {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        color: white;
        font-weight: bold;
        font-size: 14px;
        margin-right: 10px;
      }
      .method.get { background-color: #61affe; }
      .method.post { background-color: #49cc90; }
      .method.put { background-color: #fca130; }
      .method.delete { background-color: #f93e3e; }
      .path {
        font-family: monospace;
        font-size: 16px;
        font-weight: bold;
      }
      pre {
        background-color: #f1f1f1;
        padding: 10px;
        border-radius: 4px;
        overflow-x: auto;
      }
      .workflow {
        background-color: #f8f9fa;
        border-left: 4px solid #9b59b6;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 4px;
      }
      .workflow-step {
        margin-bottom: 15px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
      }
      th, td {
        padding: 8px 12px;
        border: 1px solid #ddd;
        text-align: left;
      }
      th {
        background-color: #f2f2f2;
      }
    </style>
  </head>
  <body>
    <h1>${docs.title}</h1>
    <p>${docs.description}</p>
    <p><strong>Version:</strong> ${docs.version}</p>
    <p><strong>Base URL:</strong> ${docs.baseUrl}</p>
    
    <h2>Endpoints</h2>
    ${docs.endpoints.map((endpoint: any) => `
      <div class="endpoint">
        <div>
          <span class="method ${endpoint.method.toLowerCase()}">${endpoint.method}</span>
          <span class="path">${endpoint.path}</span>
        </div>
        <p>${endpoint.description}</p>
        
        ${endpoint.parameters ? `
          <h3>Parameters</h3>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>In</th>
                <th>Required</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              ${endpoint.parameters.map((param: any) => `
                <tr>
                  <td>${param.name}</td>
                  <td>${param.in}</td>
                  <td>${param.required ? 'Yes' : 'No'}</td>
                  <td>${param.description}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : ''}
        
        ${endpoint.requestBodyExample ? `
          <h3>Request Body Example</h3>
          <pre><code>${JSON.stringify(endpoint.requestBodyExample, null, 2)}</code></pre>
        ` : ''}
        
        ${endpoint.requestBodyExamples ? `
          <h3>Request Body Examples</h3>
          ${Object.entries(endpoint.requestBodyExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${JSON.stringify(example, null, 2)}</code></pre>
          `).join('')}
        ` : ''}
        
        ${endpoint.responseExample ? `
          <h3>Response Example</h3>
          <pre><code>${JSON.stringify(endpoint.responseExample, null, 2)}</code></pre>
        ` : ''}
        
        ${endpoint.responseExamples ? `
          <h3>Response Examples</h3>
          ${Object.entries(endpoint.responseExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${JSON.stringify(example, null, 2)}</code></pre>
          `).join('')}
        ` : ''}
        
        <h3>cURL Example</h3>
        ${endpoint.curlExample ? `
          <pre><code>${endpoint.curlExample}</code></pre>
        ` : ''}
        
        ${endpoint.curlExamples ? `
          ${Object.entries(endpoint.curlExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${example}</code></pre>
          `).join('')}
        ` : ''}
      </div>
    `).join('')}
    
    <h2>Common Workflows</h2>
    ${docs.workflows.map((workflow: any) => `
      <div class="workflow">
        <h3>${workflow.name}</h3>
        <p>${workflow.description}</p>
        
        <div class="workflow-steps">
          ${workflow.steps.map((step: any) => `
            <div class="workflow-step">
              <p>${step.description}</p>
              <pre><code>${step.command}</code></pre>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('')}
    
    <h2>Request Format Guide</h2>
    <h3>File System Operations</h3>
    <pre><code>${JSON.stringify(docs.requestFormats.fileSystem, null, 2)}</code></pre>
    
    <h3>API Operations</h3>
    <pre><code>${JSON.stringify(docs.requestFormats.api, null, 2)}</code></pre>
  </body>
  </html>
    `;
}

// Start server
app.listen(PORT, () => {
  console.log(`MCP server running on port ${PORT}`);
  console.log(`Base directory for file operations: ${process.env.BASE_DIR || './data'}`);
});

// Error handling
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});