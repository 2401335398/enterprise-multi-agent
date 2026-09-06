from app.tools.base import BaseTool


class BrowserTool(BaseTool):

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "读取指定网页的详细内容。"
            "当前版本为 Mock 实现，"
            "后续通过 MCP 接入真实 Browser。"
        )

    async def run(
        self,
        url: str
    ) -> dict:

        return {
            "url": url,
            "content": (
                "当前 Browser Tool "
                "尚未接入真实网页读取能力。"
            )
        }
