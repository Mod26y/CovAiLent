import logging
import importlib
import pkgutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ValidationError

from mcp_server.tool_base import MCPTool
from tools import __path__ as tools_path

# ----------------------------------------------------
# Configuration & Logging
# ----------------------------------------------------
logger = logging.getLogger("mcp_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ----------------------------------------------------
# FastAPI Initialization
# ----------------------------------------------------
app = FastAPI(
    title="CovAIlent MCP Server",
    version="1.0.0",
    description="A central MCP dispatcher for dynamically loaded tools",
)

# ----------------------------------------------------
# Tool Registry
# ----------------------------------------------------
_TOOL_REGISTRY: Dict[str, MCPTool] = {}


def load_tools() -> None:
    """
    Dynamically discover, load, and register all MCPTool subclasses
    under the `tools/` package.
    """
    for finder, module_name, is_pkg in pkgutil.iter_modules(tools_path):
        full_module = f"tools.{module_name}"
        try:
            module = importlib.import_module(full_module)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, MCPTool) and attr is not MCPTool:
                    tool_instance = attr()
                    name = tool_instance.name
                    if name in _TOOL_REGISTRY:
                        logger.warning(f"Tool '{name}' is already registered; skipping duplicate.")
                    else:
                        _TOOL_REGISTRY[name] = tool_instance
                        logger.info(f"Loaded tool: {name}")
        except Exception as e:
            logger.error(f"Failed to load module '{full_module}': {e}")


@app.on_event("startup")
async def startup_event() -> None:
    """FastAPI startup handler to populate tool registry."""
    load_tools()


# ----------------------------------------------------
# Pydantic Models for API
# ----------------------------------------------------
class ToolListItem(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


# ----------------------------------------------------
# API Endpoints
# ----------------------------------------------------
@app.get("/tools", response_model=List[ToolListItem], summary="List all registered MCP tools")
def list_tools() -> List[ToolListItem]:
    """Return metadata for all registered tools."""
    return [
        ToolListItem(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema.schema(),
            output_schema=tool.output_schema.schema(),
        )
        for tool in _TOOL_REGISTRY.values()
    ]


@app.post("/tools/{tool_name}/run", summary="Invoke a specific tool by name")
async def run_tool(tool_name: str, payload: Dict[str, Any]) -> JSONResponse:
    """
    Validate input against the tool's Pydantic schema, execute the tool,
    validate output, and return JSON response.
    """
    tool = _TOOL_REGISTRY.get(tool_name)
    if not tool:
        logger.error(f"Tool '{tool_name}' not found in registry.")
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found.")

    try:
        validated_input = tool.input_schema(**payload)
    except ValidationError as ve:
        logger.error(f"Input validation failed for '{tool_name}': {ve}")
        raise HTTPException(status_code=422, detail=ve.errors())

    try:
        raw_output = tool.run(validated_input)
    except Exception as e:
        logger.exception(f"Execution error in tool '{tool_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error executing tool '{tool_name}': {e}")

    try:
        validated_output = tool.output_schema(**raw_output)
    except ValidationError as ve:
        logger.error(f"Output validation failed for '{tool_name}': {ve}")
        raise HTTPException(status_code=500, detail=f"Invalid output from tool '{tool_name}'.")

    return JSONResponse(content=validated_output.dict())


# ----------------------------------------------------
# Custom OpenAPI Schema
# ----------------------------------------------------
def custom_openapi() -> Dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
