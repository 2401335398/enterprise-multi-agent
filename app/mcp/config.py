from dataclasses import dataclass, field


@dataclass
class MCPServerConfig:
    name: str

    command: str

    args: list[str] = field(
        default_factory=list
    )

    env: dict[str, str] | None = None
