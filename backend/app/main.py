from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from training.router import router as training_router

app = FastAPI(
    title="Time Series Analysis API",
    description="Backend API for Time Series Analysis Application",
    version="1.0.0"
)

# Настройка CORS для работы с Vue.js фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vue.js dev server
        "http://localhost:3000",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Time Series Analysis API is running"
    }

app.include_router(training_router)
