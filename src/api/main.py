from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.generate import router
from src.api.routes.status import router as status_router
from src.api.routes.revise import router as revise_router
from src.api.routes.finish import router as finish_router
from src.api.routes.files import router as files_router
from src.endpoints.transcribe import router as transcribe_router

app = FastAPI(title="Podcast Generation API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(status_router)
app.include_router(revise_router)
app.include_router(finish_router)
app.include_router(files_router)
app.include_router(transcribe_router, prefix="/api")


@app.on_event("shutdown")
async def shutdown():
    from src.api.job_queue import get_model_manager_instance
    mm = get_model_manager_instance()
    mm.unload_all()
