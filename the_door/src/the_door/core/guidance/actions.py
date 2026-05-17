from dataclasses import dataclass, asdict
from typing import Literal

ActionContext = Literal["cli", "mcp", "viewer", "after_error"]


@dataclass(frozen=True)
class NextAction:
    id: str
    title: str
    rationale: str
    priority: int
    cli_command: str | None = None
    mcp_tool: str | None = None
    mcp_arguments: dict | None = None
    viewer_route: str | None = None

    def __post_init__(self):
        forms = sum(x is not None for x in (self.cli_command, self.mcp_tool, self.viewer_route))
        if forms != 1:
            raise ValueError("NextAction: exactly one of cli_command/mcp_tool/viewer_route must be set")
        if self.mcp_tool is not None and self.mcp_arguments is None:
            raise ValueError("NextAction: mcp_arguments required when mcp_tool is set")


def to_json_dict(action: NextAction) -> dict:
    return asdict(action)
