from dotenv import load_dotenv

load_dotenv()

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models.database import init_db
from routes.account_aggregator import router as aa_router
from routes.application import router as application_router
from routes.contact import router as contact_router
from routes.pdf_parse import router as pdf_router
from routes.score import router as score_router

app = FastAPI(
    title="GraamCredit API",
    description="AI-powered rural microloan eligibility checker for India",
    version="1.0.0",
)

_raw_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
)
cors_origins = [o.strip() for o in _raw_origins.split(",")]
# "null" covers file:// origin (opening HTML directly without Live Server)
cors_origins += ["null", "http://localhost:3000", "http://localhost:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,   # must be False when allow_origins includes "null"
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(aa_router, prefix="/api")
app.include_router(application_router, prefix="/api")
app.include_router(contact_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
app.include_router(score_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "GraamCredit API is running",
        "docs": "/docs",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
