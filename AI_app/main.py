# ai_app/main.py
from fastapi import FastAPI
#from AI_app.api.websocket import ws_router
from AI_app.api.rest import rest_router
from AI_app.config import settings
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
    app = FastAPI()
    #app.include_router(ws_router)
    app.include_router(rest_router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_app.main:app",
        host=settings.http_host,
        port=settings.http_port,
        reload=True,
    )
    
#uvicorn AI_app.main:app --host 0.0.0.0 --port 8002