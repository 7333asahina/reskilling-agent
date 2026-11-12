"""MCP サーバーから受け取ったツール定義を見る（第8回 2-2。リポジトリ直下に置く）。

    py show_tools.py           Mac は python3 show_tools.py

CLI で見た tools/list の答えが、Bedrock に渡す toolSpec の形に直されています。
inputSchema の中身は変わらず、{"json": …} で包まれているだけです。
"""

import json

from app import mcp_client

specs = mcp_client.list_tools()

print([s["toolSpec"]["name"] for s in specs])
print()

if specs:
    print("--- 1つぶんを丸ごと ---")
    print(json.dumps(specs[-1], ensure_ascii=False, indent=2)[:500])
