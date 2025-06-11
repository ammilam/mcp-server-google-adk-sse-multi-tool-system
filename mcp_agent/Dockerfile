# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the package and main.py
COPY ./mcp_agent ./mcp_agent
COPY main.py setup.py ./

# Install the package in development mode
RUN pip install -e .

# Make port 8080 available to the world outside this container
EXPOSE 8000

# Define environment variable for the port (Cloud Run compatibility, GKE will also use this)
ENV PORT 8000
ENV GOOGLE_CLOUD_LOCATION "us-central1"
ENV GOOGLE_GENAI_USE_VERTEXAI "True"
ENV MCP_SERVER_URL http://localhost:9000
COPY application_default_credentials.json /app
# You can also set MCP_SERVER_URL here if it's fixed, or prefer to set it in deployment.yaml
ENV MCP_SERVER_URL http://host.docker.internal:9000
ENV GOOGLE_APPLICATION_CREDENTIALS /app/application_default_credentials.json

# Create .dockerignore file if not exists to exclude sessions.db
RUN echo "sessions.db" > .dockerignore

# Run main.py when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]