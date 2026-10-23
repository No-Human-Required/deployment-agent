"""Tool registry for the DevOps agent."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from app.agent.context import AgentContext
from app.agent.tools.docs import build_docs_tools
from app.agent.tools.files import build_file_tools
from app.agent.tools.liara import GATED_TOOLS, build_liara_tools

FINISH_TOOL = "finish"
DEPLOY_TOOL = "liara_deploy"

__all__ = ["DEPLOY_TOOL", "FINISH_TOOL", "GATED_TOOLS", "build_tools"]


def build_tools(ctx: AgentContext) -> list[BaseTool]:
    return [*build_docs_tools(ctx), *build_file_tools(ctx), *build_liara_tools(ctx)]
