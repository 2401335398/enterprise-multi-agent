from app.tools.base import BaseTool


class SearchTool(BaseTool):

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "搜索外部公开信息。"
            "当前版本为模拟实现，"
            "后续将通过 MCP 接入真实搜索服务。"
        )

    async def run(
        self,
        query: str
    ) -> dict:

        return {
            "query": query,

            "results": [
                {
                    "title":
                        "Mock search result",

                    "content":
                        (
                            "当前 Search Tool "
                            "尚未接入真实互联网搜索。"
                        )
                }
            ]
        }
