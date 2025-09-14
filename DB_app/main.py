from fastapi import FastAPI
from DB_app.config import settings
from DB_app.db.session import init_db, dispose_db
from DB_app.api.chart_ws import chart_router
from DB_app.api.rest import rest_router
from logging.config import dictConfig

dictConfig({
    "version": 1,
    "disable_existing_loggers": False,     # 기존 uvicorn 로거 유지
    "formatters": {
        "plain": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "loggers": {
        "": {"handlers": ["console"], "level": "INFO"},
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
})

def create_app() -> FastAPI:
    app = FastAPI(title="Game API")

    # 라우터 등록
    app.include_router(rest_router)   # ← REST (/users, /progress/{id}, /clear)
    app.include_router(chart_router)  # (기존) /chart

    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.on_event("shutdown")
    async def shutdown():
        await dispose_db()

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("DB_app.main:app",
                host=settings.http_host,
                port=settings.http_port,
                reload=True)

#uvicorn DB_app.main:app --host 0.0.0.0 --port 8001 --ssl-certfile "C:\Users\han20\Documents\DalgonaBurger_Develop\server\certs\192.168.55.82.pem" --ssl-keyfile  "C:\Users\han20\Documents\DalgonaBurger_Develop\server\certs\192.168.55.82-key.pem
