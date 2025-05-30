from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from training.router import router as training_router
from prediction.router import router as prediction_router
from db.router import router as db_router
from train_prediciton_save.router import router as train_prediction_save_router
import logging
import os


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

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Time Series Analysis API is running"
    }

app.include_router(training_router)
app.include_router(train_prediction_save_router)
app.include_router(prediction_router)
app.include_router(db_router)