import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")


def test_audit_tool_over_stdio():
    from mcp.client.stdio import stdio_client

    async def audit():
        params = mcp.StdioServerParameters(
            command=sys.executable,
            args=["-m", "skill_doctor", "mcp"],
        )
        async with (
            stdio_client(params) as (reader, writer),
            mcp.ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=10)
            ) as session,
        ):
            await session.initialize()
            listing = await session.list_tools()
            assert [tool.name for tool in listing.tools] == ["audit_skill"]
            target = Path(__file__).parent / "fixtures" / "valid"
            result = await session.call_tool("audit_skill", {"target": str(target.resolve())})
            assert not result.isError
            assert len(result.structuredContent["skills"]) == 1
            invalid = await session.call_tool("audit_skill", {"target": "relative"})
            assert invalid.isError

    asyncio.run(audit())
