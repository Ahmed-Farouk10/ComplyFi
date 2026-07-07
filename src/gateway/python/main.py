from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from src.observability.tracing import setup_tracing
from src.gateway.python.routes import router

ENV_PATH = Path("D:/Microsoft-Azure-Career-Build/.env")
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    app.state.openai_client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    app.state.model = model

    setup_tracing()

    yield

    await app.state.openai_client.close()


app = FastAPI(
    title="Fintech Compliance Automation Platform",
    description="Automated KYC/AML verification, sanctions screening, fraud detection, and regulatory reporting with SOC 2 / PCI-DSS / GDPR-ready audit trails",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
