import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.device_controller import device_controller
from app.controllers.record_controller import record_controller
from app.controllers.mutate_controller import mutate_controller

os.environ["PATH"] += ":/opt/android/sdk/platform-tools"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # 允许 Vue 前端访问
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# Register router
app.include_router(device_controller.router)
app.include_router(record_controller.router)
app.include_router(mutate_controller.router)

# uvicorn app.main:app --reload
