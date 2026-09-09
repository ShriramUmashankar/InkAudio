from fastapi import FastAPI

from src.api.routes.generate import router
from src.api.routes.status import router as status_router
from src.api.routes.revise import router as revise_router
from src.api.routes.finish import router as finish_router
from src.api.routes.files import router as files_router

app = FastAPI(title="Podcast Generation API", version="1.0.0")

app.include_router(router)
app.include_router(status_router)
app.include_router(revise_router)
app.include_router(finish_router)
app.include_router(files_router)
