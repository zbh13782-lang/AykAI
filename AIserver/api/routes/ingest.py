import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from api.dependencies import get_services
from api.security import verify_internal_request
from api.schemas.request import IngestRequest
from api.schemas.response import IngestResponse

router = APIRouter()
logger = logging.getLogger(__name__)

#接受文档接口
@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, owner_id: str = Depends(verify_internal_request)) -> IngestResponse:
    logger.info(
        "ingest_start doc_id=%s source=%s content_len=%s",
        req.doc_id,
        req.source,
        len(req.content),
    )
    services = get_services()
    try:
        metadata = dict(req.metadata or {})
        metadata["owner_id"] = owner_id
        state = await run_in_threadpool(
            services["ingest_graph"].invoke,
            {
                "doc_id": req.doc_id,
                "source": req.source,
                "content": req.content,
                "metadata": metadata,
            },
        )
        logger.info(
            "ingest_done doc_id=%s inserted_parents=%s inserted_children=%s",
            req.doc_id,
            state.get("inserted_parents", 0),
            state.get("inserted_children", 0),
        )
        return IngestResponse(
            status="ok",
            inserted_parents=state.get("inserted_parents", 0),
            inserted_children=state.get("inserted_children", 0),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest_failed doc_id=%s error=%s", req.doc_id, exc)
        raise HTTPException(status_code=500, detail=f"ingest failed: {exc}") from exc
