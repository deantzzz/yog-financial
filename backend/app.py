import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.infrastructure import IFlyTekOCRClient, configure_ocr_client
from backend.routes import upload, workspace, calc


def create_app() -> FastAPI:
    app = FastAPI(title="Yog Financial Payroll API", version="0.0.1")

    app_id = os.getenv("IFLYTEK_APP_ID")
    api_key = os.getenv("IFLYTEK_API_KEY")
    api_secret = os.getenv("IFLYTEK_API_SECRET")
    if app_id and api_key and api_secret:
        host = os.getenv("IFLYTEK_OCR_HOST") or "https://webapi.xfyun.cn/v1/service/v1/ocr/recognize_table"
        client = IFlyTekOCRClient(app_id=app_id, api_key=api_key, api_secret=api_secret, host=host)
        configure_ocr_client(client)

    origins_env = os.getenv("API_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    if not origins:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router, prefix="/api")
    app.include_router(workspace.router, prefix="/api")
    app.include_router(calc.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        """Provide a lightweight landing page for container checks."""
        return JSONResponse(
            {
                "message": "Yog Financial Payroll API",
                "docs": "/docs",
                "health": "/api/workspaces",
            }
        )

    return app


app = create_app()
