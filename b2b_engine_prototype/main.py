from fastapi import FastAPI
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
