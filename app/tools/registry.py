from app.tools.search import SearchTool
from app.tools.browser import BrowserTool
from app.tools.document import DocumentSearchTool
from app.tools.calculator import CalculatorTool


TOOL_REGISTRY = {

    "search":
        SearchTool(),

    "browser":
        BrowserTool(),

    "document_search":
        DocumentSearchTool(),

    "calculator":
        CalculatorTool(),
}


def get_tool(
    name: str
):

    tool = TOOL_REGISTRY.get(
        name
    )

    if tool is None:

        raise ValueError(
            f"Unknown tool: {name}"
        )

    return tool


def list_tools() -> list[str]:

    return list(
        TOOL_REGISTRY.keys()
    )


def get_tool_descriptions() -> dict[str, str]:

    return {
        name: tool.description
        for name, tool
        in TOOL_REGISTRY.items()
    }

def register_tool(
    tool
) -> None:

    if tool.name in TOOL_REGISTRY:

        raise ValueError(
            f"Tool already registered: "
            f"{tool.name}"
        )

    TOOL_REGISTRY[
        tool.name
    ] = tool

def upsert_tool(
    tool
) -> None:

    TOOL_REGISTRY[
        tool.name
    ] = tool
