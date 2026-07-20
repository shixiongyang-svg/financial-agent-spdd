"""Financial Helpdesk Agent — FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .agent.runner import AgentRunner
from .routers.agent import router as agent_router
from .core.config import get_settings
from .core.database import create_engine_from_settings, create_session_factory
from .core.logging import bind_request_id, configure_logging, reset_request_id
from .core.services_container import ServicesContainer
from .services.llm_client import LLMHTTPClient
from .services.llm_service import LLMService
from .services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_format)
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)

    if settings.llm_provider == "openrouter":
        http_client = LLMHTTPClient(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
    else:
        http_client = LLMHTTPClient(base_url=settings.ollama_base_url)

    llm_service = LLMService(settings=settings, http_client=http_client)
    app.state.container = ServicesContainer(
        settings=settings,
        session_factory=session_factory,
        llm=llm_service,
        retrieval=RetrievalService(session_factory=session_factory, llm=llm_service),
    )
    app.state.runner = AgentRunner(app.state.container)
    try:
        yield
    finally:
        await http_client.close()
        engine.dispose()


app = FastAPI(title="Financial Helpdesk Agent", version="0.0.0", lifespan=lifespan)

app.include_router(agent_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-Id", str(uuid4()))
    token = bind_request_id(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        logger.info(
            "request_completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "duration_ms": duration_ms,
            },
        )
        reset_request_id(token)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok"}
