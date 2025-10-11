from fastapi import FastAPI

from backend.routes import upload, workspace, calc


def create_app() -> FastAPI:
    app = FastAPI(title="Yog Financial Payroll API", version="0.0.1")

    app.include_router(upload.router, prefix="/api")
    app.include_router(workspace.router, prefix="/api")
    app.include_router(calc.router, prefix="/api")

    return app


app = create_app()
