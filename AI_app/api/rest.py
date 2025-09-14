# ai_app/api/rest.py
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from AI_app.llm.generator import PromptRequest, generate_action  # PromptRequest, ActionResponse 가정
import logging

log = logging.getLogger(__name__)
rest_router = APIRouter()

@rest_router.get("/healthz")
async def healthz():
    return {"status": "ok"}

@rest_router.post("/ai/command")
async def ai_rest(req: PromptRequest):
    log.info("[AI][REST] ⇐ user=%s stage=%s prompt=%r", req.userId, req.stageId, req.prompt)
    try:
        res = await generate_action(req)  # generate_action 이 async 임을 가정
    except ValidationError as e:
        # generate_action 내부에서 모델 검증 오류가 났을 때
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"요청 검증 오류: {e}"
        )
    except Exception as e:
        log.exception("LLM 호출 중 오류")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류: {e}"
        )

    payload = res.model_dump() if hasattr(res, "model_dump") else res
    log.info("[AI][REST] ⇒ code=%s, len=%s, err=%s", getattr(res, "code", None), getattr(res, "promptLen", None), getattr(res, "error", None))
    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)
