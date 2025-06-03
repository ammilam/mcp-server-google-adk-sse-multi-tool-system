## API Call Examples

### Generate Session

```bash
export SESSION=$(curl -X POST localhost:8080/api/session|jq -r '.sessionId')
```

### Hello World Endpoint

```bash
curl -X POST http://localhost:8080/api/session/$SESSION/api \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "hello",
    "method": "GET"
  }'
  ```

  ### Echo Endpoint

  ```bash
  curl -X POST http://localhost:8080/api/session/$SESSION/api \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "echo",
    "method": "POST",
    "data": {
      "message": "Hello, world!"
    }
  }'
  ```

  ### Read File Endpoint

```bash
curl -X POST http://localhost:8080/api/session/$SESSION/filesystem \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "read",
    "path": "file.txt"
  }'
  ```

  ### Write File Endpoint

```bash
curl -X POST http://localhost:8080/api/session/$SESSION/filesystem \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "write",
    "path": "test.txt",
    "content": "Hello, world!"
  }'
  ```

### Test ADK Endpoint

```bash
curl -X POST http://localhost:8080/api/adk-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "tool_name": "file_system",
    "parameters": {
      "operation": "write",
      "path": "test.txt",
      "content": "Hello, world!"
    },
    "request_id": "test-request-1"
  }'
  ```