from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from training.router import router as training_router
from prediction.router import router as prediction_router
from db.router import router as db_router
from train_prediciton_save.router import router as train_prediction_save_router
from logs.router import router as logs_router
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
        "http://localhost:4173",  # Vue.js production preview
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

def ensure_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('SECRET_KEY=KIgSBcy5vZ\n')

ensure_env_file()

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
app.include_router(logs_router)