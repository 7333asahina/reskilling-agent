"""tool の本数と入力トークンの関係を数える（第8回 2-4。リポジトリ直下に置く）。

    py count_tools.py          Mac は python3 count_tools.py

同じ質問を2回送ります。1回目は手元の tool だけ、2回目は MCP の tool も足します。
質問は変えていないのに、入力トークンが増えます。
"""

import boto3

from app import mcp_client
from app.config import settings
from app.prompt import build_system_prompt
from app.tools import all_tool_specs

client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
system = [{"text": build_system_prompt()}]
question = [{"role": "user", "content": [{"text": "今週の予定を教えて"}]}]

# **本数はハードコードしない。**第8回は MCP が3つだが、第9回で社内名簿が2つ増え、
# 名簿サーバーを起こしているかどうかでも変わる。数えたものをそのまま出す
mcp_tools = mcp_client.list_tools()

for label, tools in [
    ("手元1つだけ", all_tool_specs()),
    (f"手元1つ + MCP {len(mcp_tools)}つ", all_tool_specs() + mcp_tools),
]:
    res = client.converse(
        modelId=settings.bedrock_model_id,
        system=system,
        messages=question,
        toolConfig={"tools": tools},
        # maxTokens は普段のまま。5 のような小さい値にすると、tool を呼ぼうとした
        # 途中で切れて ModelErrorException になる
        inferenceConfig={"maxTokens": settings.max_tokens, "temperature": settings.temperature},
    )
    names = [b["toolUse"]["name"] for b in res["output"]["message"]["content"] if "toolUse" in b]
    print(f'{label:20} 入力 {res["usage"]["inputTokens"]}  stopReason {res["stopReason"]}  {names}')
