"""エージェントの本体（第7回。app/agent.py として新しく置き、app/llm.py は消す）。

**エージェントと呼んでいるものの正体は、この関数の中の for ループひとつ。**

    1. モデルに聞く
    2. 「この tool をこの引数で使いたい」と言われたら、こちらで動かして結果を返す
    3. 1 に戻る
    4. 「答えが出た」と言われたら終わり

第6回に CLI で手でやった往復と同じ。違うのは messages を組み立てるのが自分ではないことだけ。
魔法は無い。止める条件（MAX_AGENT_TURNS）を人間が決めているのも、この形だから。

第6回の llm.py との違いは3つ。
  1. toolConfig を毎ターン渡す（app/tools.py）
  2. stopReason が tool_use の間まわる（llm.py は1回で返していた）
  3. モデルの考えた過程（<thinking>）を落としてから画面と履歴に渡す
"""

import logging
import re
import time
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings
from app.prompt import build_system_prompt
from app.tools import all_tool_specs, run_tool

logger = logging.getLogger(__name__)

_client = boto3.client(
    "bedrock-runtime",
    region_name=settings.aws_region,
    config=Config(
        retries={"max_attempts": 2, "mode": "standard"},
        read_timeout=30,
        connect_timeout=5,
    ),
)

# ツール定義を渡すと、このモデルは判断の過程を本文に混ぜて返す（第6回 02 の 2-4）。
# system に「タグを出力しない」と書いても完全には止まらないので、コードで消す
_THINKING = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    cleaned = _THINKING.sub("", text)
    # maxTokens で切れると閉じタグが付かないまま返る。残ったタグも落とす
    cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _clean(message: dict[str, Any]) -> dict[str, Any]:
    """モデルの発言から <thinking> を落とした複製を返す。

    画面に出すときだけ落とすのでは足りない。**落とさないまま履歴に残すと、次のリクエストで
    モデルに送り返される。**考えた過程は次の判断の役に立たないのに、入力トークンだけが増える。

    toolUse のブロックはそのまま残す。ここを落とすと、直後の toolResult と対応が取れなくなる。
    """
    blocks: list[dict[str, Any]] = []
    for block in message.get("content", []):
        if "text" not in block:
            blocks.append(block)
            continue
        text = _strip_thinking(block["text"])
        if text:
            blocks.append({"text": text})
    if not blocks:                      # 考えた過程しか無かったとき。空の content は API が受け付けない
        blocks = [{"text": "（応答が空でした）"}]
    return {**message, "content": blocks}


def run_agent(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """1回の発話を処理して、答えと実測値を返す。

    返す辞書の項目は main.py の ChatResponse に合わせてある。
    messages は tool の往復を含む会話の全部で、そのまま履歴に保存する。
    """
    started = time.monotonic()
    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": [{"text": message}]})

    total_in = total_out = 0
    tools_used: list[str] = []

    # `tool` の一覧と system はターンの前に1回だけ用意して、まわるあいだ使い回す
    tool_specs = all_tool_specs()
    system = [{"text": build_system_prompt()}]

    for turn in range(1, settings.max_agent_turns + 1):
        response = _client.converse(
            modelId=settings.bedrock_model_id,
            system=system,
            messages=messages,
            toolConfig={"tools": tool_specs},
            inferenceConfig={
                "maxTokens": settings.max_tokens,
                "temperature": settings.temperature,
            },
        )

        usage = response.get("usage", {})
        total_in += usage.get("inputTokens", 0)
        total_out += usage.get("outputTokens", 0)
        stop_reason = response.get("stopReason")
        # 履歴に積む前に考えた過程を落とす。ここで落とせば画面にも履歴にも残らない
        assistant = _clean(response["output"]["message"])
        messages.append(assistant)

        logger.info("bedrock turn finished", extra={"extra_fields": {
            "turn": turn,
            "stop_reason": stop_reason,
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        }})

        if stop_reason != "tool_use":       # tool を使いたいと言われていない ＝ 答えが出た
            text = "".join(b.get("text", "") for b in assistant["content"] if "text" in b)
            return {
                "reply": text.strip() or "（応答が空でした）",
                "messages": messages,
                "turns": turn,
                "tools_used": tools_used,
                "input_tokens": total_in,
                "output_tokens": total_out,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "stop_reason": stop_reason,
            }

        # 1回の応答で tool を2つ以上指名してくることがあるので、全部動かす
        tool_results = []
        for block in assistant["content"]:
            if "toolUse" not in block:
                continue
            use = block["toolUse"]
            tools_used.append(use["name"])
            result = run_tool(use["name"], use["input"])
            tool_results.append({
                "toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": result}]}
            })

        messages.append({"role": "user", "content": tool_results})   # 結果は user で返す

    # ここに来る ＝ MAX_AGENT_TURNS 回まわっても答えが出なかった。
    # 打ち切るのが正しい。放置するとモデルが tool を呼び続けて課金だけが増える
    logger.warning("agent hit max turns",
                   extra={"extra_fields": {"max_turns": settings.max_agent_turns}})
    return {
        "reply": f"（{settings.max_agent_turns}回考えましたが答えをまとめられませんでした。質問を分けて聞いてみてください）",
        "messages": messages,
        "turns": settings.max_agent_turns,
        "tools_used": tools_used,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stop_reason": "max_turns",
    }
