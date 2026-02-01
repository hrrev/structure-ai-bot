import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_assisted_automation.api.routes import router
from ai_assisted_automation.registry.tool_registry import ToolRegistry
from ai_assisted_automation.storage.json_store import JsonStore


def create_app(
    data_dir: str | None = None,
    tools_dir: str | None = None,
    tool_configs: dict | None = None,
) -> FastAPI:
    app = FastAPI(title="Workflow Automation Engine")
    app.include_router(router)

    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        def index():
            return FileResponse(str(static_dir / "index.html"))

    @app.on_event("startup")
    def startup():
        app.state.store = JsonStore(data_dir or os.environ.get("DATA_DIR", "data"))
        registry = ToolRegistry()
        td = tools_dir or os.environ.get("TOOLS_DIR", "tools")
        if Path(td).is_dir():
            registry.load_directory(td)
        app.state.registry = registry
        app.state.tool_configs = tool_configs or {}

    return app
