import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic (e.g., DB connection, Qdrant check)
    print("🚀 AutoCode Sage Service Starting...")
    yield
    # Shutdown logic
    print("🛑 AutoCode Sage Service Stopping...")

app = FastAPI(title="AutoCode Sage", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "AutoCode Sage"}

# Import routers (to be created later)
from routers import webhooks
app.include_router(webhooks.router)
