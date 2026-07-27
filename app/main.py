import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.webrtc import router as webrtc_router

# Load .env from the project root so provider keys are available at runtime.
# python-dotenv was already a declared dependency; calling it here is what makes
# the .env file actually take effect.
load_dotenv()

# Surface app-level INFO logs (event flow, STT diagnostics) under uvicorn.
# Set on both the "app" namespace and explicitly on "app.webrtc" because
# uvicorn's logging config can leave child loggers at WARNING otherwise.
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.webrtc").setLevel(logging.INFO)

WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI(title="Fluid Voice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(webrtc_router)

# Mount the built frontend last so it never shadows API routes defined above.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
