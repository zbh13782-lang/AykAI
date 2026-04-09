import logging
import time

from fastapi import FastAPI
from fastapi import Request

from config.settings import get_settings
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router
from api.routes.query import router as query_router
from src.common.logging_config import setup_logging

settings = get_settings()
setup_logging(level=settings.log_level, log_file_path=settings.log_file_path)
logger = logging.getLogger(__name__)

app = FastAPI(title="AykAI API", version="0.1.0")

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(query_router, prefix="/api", tags=["query"])


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
	start = time.perf_counter()
	response = await call_next(request)
	duration_ms = int((time.perf_counter() - start) * 1000)
	logger.info(
		"http_request method=%s path=%s status=%s duration_ms=%s",
		request.method,
		request.url.path,
		response.status_code,
		duration_ms,
	)
	return response