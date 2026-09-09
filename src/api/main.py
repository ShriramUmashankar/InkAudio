from fastapi import FastAPI

from src.api.routes.generate import router
from src.api.routes.status import router as status_router

app = FastAPI(title="Podcast Generation API", version="1.0.0")

app.include_router(router)
app.include_router(status_router)
