import uvicorn
from fastapi import FastAPI
from app.api import router as video_assets_router
from fastapi.staticfiles import StaticFiles


app = FastAPI()
app.include_router(video_assets_router)

app.mount("/audio", StaticFiles(directory="."), name="audio")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)