# DB_app/api/rest.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, field_validator, conint
from sqlalchemy import select, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
import logging
from datetime import datetime, timezone
from DB_app.db.session import async_session
from DB_app.db.models import UserORM, StageORM, UserStageProgressORM, RunLogORM

rest_router = APIRouter()
log = logging.getLogger(__name__)

class CreateUserReq(BaseModel):
    user_id: str
    profile_image: int | None = 0  # ← 기본값 0

@rest_router.post("/users")
async def create_user(req: CreateUserReq, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    log.info("[AI][REST] ⇐ user_id=%s from=%s", req.user_id, client_ip)

    created = False
    async with async_session() as s, s.begin():
        user = await s.get(UserORM, req.user_id)
        if not user:
            user = UserORM(user_id=req.user_id, profile_image=(req.profile_image or 0))
            s.add(user)
            created = True

    # DB에 있는 실제 값을 반환
    return {"user_id": req.user_id, "created": created, "profile_image": user.profile_image}

class UpdateProfileImageReq(BaseModel):
    profile_image: conint(ge=0, le=2)  # 0~2만 허용

@rest_router.patch("/users/{user_id}/profile_image")
async def update_profile_image(user_id: str, body: UpdateProfileImageReq):
    async with async_session() as s, s.begin():
        user = await s.get(UserORM, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 프로필 이미지 변경
        user.profile_image = body.profile_image

    return {
        "ok": True,
        "user_id": user_id,
        "profile_image": body.profile_image
    }    

@rest_router.get("/progress/{user_id}")
async def get_progress(user_id: str):
    async with async_session() as s:
        # 1) 유저 조회 (없으면 404)
        user = await s.get(UserORM, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 2) 진행 리스트 조회(기존대로)
        rows = (await s.execute(
            select(
                StageORM.code,
                UserStageProgressORM.unlocked,
                UserStageProgressORM.cleared,
                UserStageProgressORM.prompt_length,
                UserStageProgressORM.clear_time_ms,
                UserStageProgressORM.cleared_at,
            )
            .join(UserStageProgressORM, UserStageProgressORM.stage_id == StageORM.stage_id)
            .where(UserStageProgressORM.user_id == user_id)
            .order_by(StageORM.code)
        )).all()

    # 3) 프로필 번호를 응답에 포함
    return {
        "user_id": user_id,
        "profile_image": user.profile_image,  # ← 추가
        "stages": [
            {
                "code": r[0],
                "unlocked": r[1],
                "cleared": r[2],
                "prompt_length": r[3],
                "clear_time_ms": r[4],
                "cleared_at": (r[5].isoformat() if r[5] else None),
            } for r in rows
        ],
    }

class RunLogIn(BaseModel):
    """스테이지 종료 후 결과(로그) 수집용 페이로드"""
    user_id: str
    stage_code: str                 # 예: "A1" ~ "E5"
    prompt_length: conint(ge=0)     # 사용한 단어 수
    clear_time_ms: conint(ge=0)     # ms

    @field_validator("user_id", "stage_code")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("stage_code")
    @classmethod
    def valid_code(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"[A-E][1-5]", v):
            raise ValueError("stage_code must be A1..E5")
        return v
    
@rest_router.post("/run-logs")
async def post_run_log(payload: RunLogIn):
    try:
        rank_clear_pct = 100.0
        rank_length_pct = 100.0
        rank_clear = 1
        rank_length = 1
        total_time = 1
        total_length = 1

        async with async_session() as s, s.begin():
            # 스테이지 조회
            stage = (await s.execute(
                select(StageORM).where(StageORM.code == payload.stage_code)
            )).scalars().first()
            if not stage:
                raise HTTPException(status_code=400, detail="unknown stage_code")

            # 진행행 조회(없으면 생성)
            prog = await s.get(UserStageProgressORM, (payload.user_id, stage.stage_id))
            if not prog:
                prog = UserStageProgressORM(
                    user_id=payload.user_id,
                    stage_id=stage.stage_id,
                    unlocked=True
                )
                s.add(prog)

            # 클리어 처리/개선 여부 판정
            prog.unlocked = True
            prog.cleared = True

            new_time = int(payload.clear_time_ms)
            new_length = int(payload.prompt_length)

            improved_time = (prog.clear_time_ms is None) or (new_time < prog.clear_time_ms)
            improved_length = (prog.prompt_length is None) or (new_length < prog.prompt_length)

            if improved_time:
                prog.clear_time_ms = new_time
            if improved_length:
                prog.prompt_length = new_length
            if improved_time or improved_length:
                prog.cleared_at = datetime.now(timezone.utc)

            # 러닝 로그 적재
            s.add(RunLogORM(
                user_id=payload.user_id,
                stage_code=payload.stage_code,
                prompt_length=new_length,
                clear_time_ms=new_time,
            ))
            await s.flush()

            # --- clear_time_ms 기준 랭킹/비율 ---
            # 내가 이번에 달성한 기록(new_time)과 비교해 '더 빠른' 기록 수 (본인 제외)
            faster_time = await s.scalar(
                select(func.count()).select_from(UserStageProgressORM).where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.clear_time_ms.isnot(None),
                    tuple_(UserStageProgressORM.clear_time_ms,
                        UserStageProgressORM.cleared_at) < (prog.clear_time_ms, prog.cleared_at),
                    UserStageProgressORM.user_id != payload.user_id,
                )
            ) or 0

            # '시간 기록을 가진 유저'수 (본인 제외)
            others_time_total = await s.scalar(
                select(func.count()).select_from(UserStageProgressORM).where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.clear_time_ms.isnot(None),
                    UserStageProgressORM.user_id != payload.user_id,
                )
            ) or 0

            # 총 비교 인원 = 다른 사람 + 나(이번 기록)
            total_time = others_time_total + 1
            rank_clear = faster_time + 1
            rank_clear_pct = round((rank_clear / total_time) * 100.0, 2)

            # --- prompt_length 기준 랭킹/비율 ---
            # 내가 이번에 사용한 프롬프트 길이(new_length)보다 '더 짧은' 기록 수 (본인 제외)
            shorter_len = await s.scalar(
                select(func.count()).select_from(UserStageProgressORM).where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.prompt_length.isnot(None),
                    tuple_(UserStageProgressORM.prompt_length,
                        UserStageProgressORM.cleared_at) < (prog.prompt_length, prog.cleared_at),
                    UserStageProgressORM.user_id != payload.user_id,
                )
            ) or 0

            # '프롬프트 길이 기록을 가진 유저'수 (본인 제외)
            others_len_total = await s.scalar(
                select(func.count()).select_from(UserStageProgressORM).where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.prompt_length.isnot(None),
                    UserStageProgressORM.user_id != payload.user_id,
                )
            ) or 0

            total_length = others_len_total + 1
            rank_length = shorter_len + 1
            rank_length_pct = round((rank_length / total_length) * 100.0, 2)

            # === 리더보드: 두 부문 Top 10 (profile_image 포함) ===
            # 프롬프트 길이 부문: prompt_length ASC, 동률 cleared_at ASC
            prompt_rows = (await s.execute(
                select(
                    UserStageProgressORM.user_id,
                    UserStageProgressORM.prompt_length,
                    UserStageProgressORM.clear_time_ms,
                    UserStageProgressORM.cleared_at,
                    UserORM.profile_image,  # JOIN으로 가져오기
                )
                .join(UserORM, UserStageProgressORM.user_id == UserORM.user_id)
                .where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.prompt_length.isnot(None),
                    UserStageProgressORM.cleared_at.isnot(None),  # tie-breaker 안정성
                )
                .order_by(
                    UserStageProgressORM.prompt_length.asc(),
                    UserStageProgressORM.cleared_at.asc(),
                )
                .limit(10)
            )).all()

            prompt_top10 = [
                {
                    "user_id": r.user_id,
                    "prompt_length": int(r.prompt_length) if r.prompt_length is not None else None,
                    "clear_time_ms": int(r.clear_time_ms) if r.clear_time_ms is not None else None,
                    "profile_image": int(r.profile_image) if r.profile_image is not None else None,
                }
                for r in prompt_rows
            ]

            # 클리어 시간 부문: clear_time_ms ASC, 동률 cleared_at ASC
            time_rows = (await s.execute(
                select(
                    UserStageProgressORM.user_id,
                    UserStageProgressORM.clear_time_ms,
                    UserStageProgressORM.prompt_length,
                    UserStageProgressORM.cleared_at,
                    UserORM.profile_image,  # JOIN으로 가져오기
                )
                .join(UserORM, UserStageProgressORM.user_id == UserORM.user_id)
                .where(
                    UserStageProgressORM.stage_id == stage.stage_id,
                    UserStageProgressORM.cleared.is_(True),
                    UserStageProgressORM.clear_time_ms.isnot(None),
                    UserStageProgressORM.cleared_at.isnot(None),  # tie-breaker 안정성
                )
                .order_by(
                    UserStageProgressORM.clear_time_ms.asc(),
                    UserStageProgressORM.cleared_at.asc(),
                )
                .limit(10)
            )).all()

            time_top10 = [
                {
                    "user_id": r.user_id,
                    "prompt_length": int(r.prompt_length) if r.prompt_length is not None else None,
                    "clear_time_ms": int(r.clear_time_ms) if r.clear_time_ms is not None else None,
                    "profile_image": int(r.profile_image) if r.profile_image is not None else None,
                }
                for r in time_rows
            ]

        # 게임 결과창에서 바로 사용할 응답 (WebSocket과 동일 키 유지)
        resp = {
            "ack": True,
            "user_id": payload.user_id,
            "stage": payload.stage_code,
            "rank_clear_time_percent": rank_clear_pct,
            "rank_tokens_percent": rank_length_pct,
            "rank_clear_time": rank_clear,
            "rank_tokens": rank_length,
            "total_records": total_time,
            "received_text": "ok",
            "leaderboards": {
                "prompt_top10": prompt_top10,  # 프롬프트 길이 부문 Top 10 (profile_image 포함)
                "time_top10": time_top10,      # 클리어 시간 부문 Top 10 (profile_image 포함)
            },
        }
        return JSONResponse(status_code=200, content=resp)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"invalid payload: {e.errors()}")
    except SQLAlchemyError as e:
        log.exception("[REST][DB] error")
        raise HTTPException(status_code=500, detail="db_error")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[REST] unexpected")
        raise HTTPException(status_code=500, detail=str(e))