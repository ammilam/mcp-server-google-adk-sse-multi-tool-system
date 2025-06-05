# Base image - use Node.js LTS
FROM node:18-slim

# Set working directory
WORKDIR /app

# Install git (needed for repository operations)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy package.json and package-lock.json files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application source
COPY . .

# Create directories for file operations and repositories
RUN mkdir -p /app/data/repos && \
    chown -R node:node /app/data

# Switch to non-root user
USER node

# Set default environment variables
ENV PORT=9000
ENV BASE_DIR="/app/data"
ENV REPO_DIR="/app/data/repos"
ENV MAX_EVENT_LISTENERS=100

# Expose the port the app runs on
EXPOSE 9000

# Command to run the application
CMD ["npm", "run", "start"]