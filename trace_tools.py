"""モデルが tool に渡した引数を、そのまま画面に出す（第10回 `02` 2-1。リポジトリ直下に置く）。

    py trace_tools.py "直近のメールを1件探して、その本文を読んで要点を教えて"
    Mac は python3 trace_tools.py "..."

アプリの画面には、呼んだ tool の名前しか出ません。**渡した引数は出ません。**
app/agent.py と同じループを回しながら、モデルが渡した引数を1行ずつ表示します。

答えが合っているかどうかは、引数を見ないと分かりません。
`tool` が動いていることと、正しく使われていることは別です。
"""

import json
import sys

import boto3

from app.agent import _clean
from app.config import settings
from app.prompt import build_system_prompt
from app import mcp_client
from app.tools import all_tool_specs, run_tool

question = sys.argv[1] if len(sys.argv) > 1 else "今週の予定を教えて"

client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
tool_specs = all_tool_specs() + mcp_client.list_tools()
messages = [{"role": "user", "content": [{"text": question}]}]

print(f"質問: {question}")
print(f"渡した tool: {len(tool_specs)} 個")
print("-" * 60)

for turn in range(1, settings.max_agent_turns + 1):
    res = client.converse(
        modelId=settings.bedrock_model_id,
        system=[{"text": build_system_prompt()}],
        messages=messages,
        toolConfig={"tools": tool_specs},
        inferenceConfig={
            "maxTokens": settings.max_tokens,
            "temperature": settings.temperature,
        },
    )
    assistant = _clean(res["output"]["message"])
    messages.append(assistant)
    uses = [b["toolUse"] for b in assistant["content"] if "toolUse" in b]

    if not uses:                        # tool を使いたいと言われなかった = 答えが出た
        answer = "".join(b.get("text", "") for b in assistant["content"] if "text" in b)
        print("-" * 60)
        print(f"turns {turn}")
        print(f"答え: {answer.strip()[:200]}")
        break

    results = []
    for use in uses:
        args = json.dumps(use["input"], ensure_ascii=False)
        print(f"turn {turn}  {use['name']}  {args}")
        if mcp_client.has(use["name"]):
            out = mcp_client.call_tool(use["name"], use["input"])
        else:
            out = run_tool(use["name"], use["input"])
        results.append({
            "toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": out}]}
        })
    messages.append({"role": "user", "content": results})
