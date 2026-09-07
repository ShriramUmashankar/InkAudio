from fastapi import FastAPI

from .endpoints import transcribe


app = FastAPI(title="STT Service", version="1.0.0")

app.include_router(transcribe.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)