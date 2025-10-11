from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.routes import upload, workspace, calc


def create_app() -> FastAPI:
    app = FastAPI(title="Yog Financial Payroll API", version="0.0.1")

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
