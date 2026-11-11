""" tool の往復を Python で回す（第7回 02 の 3-1）。

    python3 tool_loop.py "いま何時？"      # Mac
    py tool_loop.py "いま何時？"           # Windows

第6回は、この往復を手でやった。1回目を打って toolUse を読み、toolResult を書いて2回目を打った。
やっていることは同じで、messages を組み立てるのが自分ではなく while ループになっただけ。

アプリとは無関係に、これ1つで動く。リポジトリ直下の tool-config.json を読む（第6回にコピーしたもの）。
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import boto3

MODEL_ID = "amazon.nova-lite-v1:0"
MAX_TURNS = 1                                   # 何ターンまでで打ち切るか
JST = timezone(timedelta(hours=9), "JST")
UTC = timezone.utc

client = boto3.client("bedrock-runtime", region_name="ap-northeast-1")

# ツール定義。第6回に CLI へ --tool-config file://tool-config.json で渡したものと同じ
tool_config = json.load(open("tool-config.json", encoding="utf-8"))


def get_current_time(timezone: str = "JST") -> dict:
    """ tool の中身。**この関数はモデルに渡さない。**渡すのは上のツール定義だけ。"""
    tz = JST if timezone.upper() == "JST" else UTC
    now = datetime.now(tz)
    return {
        "timezone": timezone.upper(),
        "readable": now.strftime("%Y年%m月%d日 %H時%M分"),
        "weekday": "月火水木金土日"[now.weekday()] + "曜日",
    }


question = sys.argv[1] if len(sys.argv) > 1 else "いま何時？"
messages = [{"role": "user", "content": [{"text": question}]}]

for turn in range(1, MAX_TURNS + 1):
    response = client.converse(
        modelId=MODEL_ID,
        messages=messages,
        toolConfig=tool_config,                 # 1ターン目も2ターン目も、毎回渡す
        inferenceConfig={"maxTokens": 200, "temperature": 0.3},
    )
    stop_reason = response["stopReason"]
    assistant = response["output"]["message"]
    messages.append(assistant)                  # モデルの発言を積む

    usage = response["usage"]
    print(f"--- {turn}ターン目  stopReason={stop_reason}  "
          f"in={usage['inputTokens']} out={usage['outputTokens']}")

    if stop_reason != "tool_use":               # tool を使いたいと言われていない ＝ 答えが出た
        text = "".join(b.get("text", "") for b in assistant["content"])
        print(text.strip())
        break

    tool_results = []
    for block in assistant["content"]:
        if "toolUse" not in block:
            continue
        use = block["toolUse"]
        print(f"    tool を呼ぶ: {use['name']} {use['input']}")
        result = get_current_time(**use["input"])
        print(f"    結果: {result}")
        tool_results.append({
            "toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": result}]}
        })

    messages.append({"role": "user", "content": tool_results})   # 結果は user で返す
else:
    print(f"{MAX_TURNS}ターンまわっても答えが出ませんでした")
