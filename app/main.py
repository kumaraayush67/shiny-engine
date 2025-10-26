from fastapi import FastAPI

from sqlmodel import SQLModel
from contextlib import asynccontextmanager
from app.database import engine
from app.batches.routes import router as batch_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    print("******* Application Startup *******")
    
    # Create tables
    SQLModel.metadata.create_all(engine)
    
    yield
    
    print("******* Application Shutdown *******")


# Initialize app
app = FastAPI(
    title="Bulk Processing app",
    description="App that helps in batching processes",
    version="0.1.0",
    lifespan=lifespan
)


# Add routes to app
app.include_router(batch_router)
