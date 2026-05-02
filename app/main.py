from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="API for magister Diploma",
    description="API for magister diploma",
    version="0.1.0"
)

# CORS palicy 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # на проде заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Список роутов
@app.post("auth/register")
async def register():
    return "auth/register"

@app.post("/auth/login",)
async def login():
    return "/auth/login"

@app.get("/tasks/materials-procurement")
async def materialsProcurement():
    return "/tasks/materials-procurement"

@app.get("/tasks/schedule-deviations")
async def materialsProcurement():
    return "/tasks/schedule-deviations"

@app.get("/tasks/warehouse-loading")
async def materialsProcurement():
    return "/tasks/warehouse-loading"

@app.get("/tasks/work-schedule")
async def materialsProcurement():
    return "/tasks/work-schedule"

if __name__ == "__main__":
    uvicorn.run(
        "main:app",          # если запускаешь из папки app/: python main.py
        host="0.0.0.0",
        port=8000,
        reload=True,         # автоперезагрузка при изменении файлов
    )
