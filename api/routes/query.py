import logging
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import get_services
from api.schemas.request import QueryRequest
from api.schemas.response import QueryResponse
from src.rag.rag_chain import stream_answer
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/query",response_model=QueryResponse)
def query(req:QueryRequest) -> QueryResponse | StreamingResponse:
    logger.info("query_start stream=%s query_len=%s", req.stream, len(req.query))
    services = get_services()
    try:
        if req.stream:
            return query_stream(req)
        state = services["query_graph"].invoke({"query":req.query})
        logger.info(
            "query_done stream=%s references=%s answer_len=%s",
            req.stream,
            len(state.get("parent_rows", [])),
            len(state.get("answer", "")),
        )
        return QueryResponse(
            status="ok",
            answer = state.get("answer",""),
            references = state.get("parent_rows", [])
        )
    except Exception as exc:
        logger.exception("query_failed stream=%s error=%s", req.stream, exc)
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc

@router.post("/query/stream")
def query_stream(req:QueryRequest) -> StreamingResponse:
    logger.info("query_start stream=%s query_len=%s", req.stream, len(req.query))
    services = get_services()

    def event_stream():
        try:
            #1.只检索，不生成答案
            state = services["query_graph"].invoke({"query":req.query,"skip_generate":True})
            refs = state.get("parent_rows", [])

            #2.发送参考资料
            logger.info("query_stream_references count=%s", len(refs))
            yield f"data: {json.dumps({'event': 'references', 'data': refs}, ensure_ascii=True)}\n\n"

            #3.流生成答案
            answer_text = ""
            for token in stream_answer(services["chat_model"],req.query,refs):
                answer_text += token
                yield f"data: {json.dumps({'event': 'token', 'data': token}, ensure_ascii=True)}\n\n"

            #4.发送完成
            logger.info("query_stream_done references=%s answer_len=%s", len(refs), len(answer_text))
            yield f"data: {json.dumps({'event': 'done', 'data': {'answer': answer_text, 'references': refs}}, ensure_ascii=True)}\n\n"
        except Exception as exc:
            logger.exception("query_stream_failed error=%s", exc)
            err = {"event": "error", "data": str(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")