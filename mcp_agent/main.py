import logging
import os
from google.adk.agents import Agent  # Updated import path
from dotenv import load_dotenv
from mcp_toolkit import get_toolkit

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-agent-runner")

# Import agent definition to ensure it's registered
from agent import agent

def main():
    """Main function to run the MCP agent interactively"""
    logger.info("Starting MCP Agent")
    
    # Initialize MCP toolkit
    toolkit = get_toolkit()
    
    try:
        # Print welcome message
        print("\n" + "="*50)
        print("MCP Agent - Interactive Mode")
        print("="*50)
        print("\nThis agent can:")
        print("  - Get current time in different cities")
        print("  - Check weather in locations")
        print("  - Work with files (read, write, list, delete)")
        print("  - Store and retrieve session data")
        print("  - Make API calls through the MCP server")
        print("  - Clone and analyze repositories from GitHub or GitLab")
        print("  - Generate documentation for code repositories")
        print("\nExample commands:")
        print("  - What's the weather in London?")
        print("  - What time is it in New York?")
        print("  - Write 'Hello world' to a file named greeting.txt")
        print("  - Read the file greeting.txt")
        print("  - List files in the current directory")
        print("  - Store my name as John")
        print("  - What is my name?")
        print("  - Call the hello API")
        print("  - Clone the repository at github.com/username/repo")
        print("  - Analyze the code from the repository I just cloned")
        print("  - Generate a README for this repository")
        print("\nType 'exit' to quit")
        print("="*50 + "\n")
        
        # Start conversation loop
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye!")
                break
                
            try:
                # Execute agent with user input
                # Using the agent instance directly instead of execute_agent_by_name
                response = agent.execute_agent(user_input)
                print(f"\nAgent: {response}")
            except Exception as e:
                logger.error(f"Error executing agent: {str(e)}")
                print(f"\nAgent: I encountered an error processing your request: {str(e)}")
            
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Error running agent: {str(e)}")
        print(f"An error occurred: {str(e)}")
    finally:
        # Stop SSE listener when exiting
        toolkit.stop_sse_listener()

if __name__ == "__main__":
    main()