"""
user-api - Web API

Generated from template: python-web-api
"""

import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# Setup structured logging
def setup_logging():
    """Setup structured logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


# Initialize app
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="user-api",
    description="Generated Web API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to user-api", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "user-api",
        "version": "1.0.0"
    }


@app.get("/api/v1/example")
async def example_endpoint():
    """Example API endpoint."""
    logger.info("Example endpoint called")
    return {
        "data": "This is example data",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/example")
async def create_example(data: dict):
    """Example POST endpoint."""
    logger.info(f"Creating example with data: {data}")
    
    # TODO: Implement your business logic here
    
    return {
        "message": "Example created successfully",
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


def load_config():
    """Load configuration from environment."""
    return {
        "port": int(os.getenv("PORT", "8000")),
        "host": os.getenv("HOST", "0.0.0.0"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "database_url": os.getenv("DATABASE_URL"),
    }


if __name__ == "__main__":
    config = load_config()
    logger.info(f"Starting user-api API with config: {config}")
    
    uvicorn.run(
        "app:app",
        host=config["host"],
        port=config["port"],
        log_level=config["log_level"].lower(),
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )
