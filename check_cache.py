"""tools/list の答えが何秒とっておかれるかを数える（第8回 2-3。リポジトリ直下に置く）。

    py check_cache.py          Mac は python3 check_cache.py

1回目はサーバーに送るので 100 ミリ秒ほど、2回目は MCP_CACHE_SECONDS のあいだ
前の答えを使うので 0 ミリ秒になります。
"""

import time

from app import mcp_client

t = time.time()
mcp_client.list_tools()
print(f"1回目 {(time.time() - t) * 1000:.0f} ms")

t = time.time()
mcp_client.list_tools()
print(f"2回目 {(time.time() - t) * 1000:.1f} ms")
