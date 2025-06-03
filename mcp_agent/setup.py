from setuptools import setup, find_packages

setup(
    name="mcp_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-adk>=1.0.0",
        "sseclient-py>=1.7.2",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mcp-agent=mcp_agent.main:main",
        ],
    },
)