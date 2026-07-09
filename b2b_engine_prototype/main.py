from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base, AsyncSessionLocal
from routers import router
from seed import seed_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application Startup
    print("Application Startup: Ensuring database tables exist...")
    async with engine.begin() as conn:
        # For production, Alembic migrations should be used instead of create_all
        await conn.run_sync(Base.metadata.create_all)
        
    print("Application Startup: Seeding initial data if empty...")
    async with AsyncSessionLocal() as session:
        await seed_data(session)
        
    yield
    # Application Shutdown
    print("Application Shutdown: Disposing database engine...")
    await engine.dispose()

app = FastAPI(
    title="Ataol Dashboard B2B API",
    description="Apollo.io Clone MVP Prototype using FastAPI, async SQLAlchemy, and PostgreSQL",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS Middleware to allow requests from the GitHub Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sertacgul.github.io", 
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*" # Temporarily allow all for prototype testing if needed, though specific is better
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the main router for API endpoints
app.include_router(router)

@app.get("/")
def read_root():
    return {
        "message": "Ataol Dashboard B2B API is running successfully.",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
