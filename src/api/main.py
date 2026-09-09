from fastapi import FastAPI

from src.api.routes.generate import router

app = FastAPI(title="Podcast Generation API", version="1.0.0")

app.include_router(router)
