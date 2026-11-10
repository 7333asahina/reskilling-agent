"""LLM を1回呼ぶ（第6回版。app/llm.py を丸ごと差し替える）。

第5回との違いは2つ。
  1. system（役割・答え方・今日の日付）を付ける         → app/prompt.py
  2. messages に「これまでの会話」を積んでから今回の発言を足す → history は呼び出し側（main.py）が渡す

**送るものと返るものの形は第5回と同じ。**modelId・messages・inferenceConfig を送り、output・usage・stopReason が返る。
system と過去の発言が増えたぶん、usage.inputTokens が増える。それがコンテキストの大きさそのもの。
"""

import logging
import time
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings
from app.prompt import build_system_prompt

logger = logging.getLogger(__name__)

# boto3 のクライアントは作るのに時間がかかる。
# モジュールの読み込み時に1回だけ作り、リクエストのたびに使い回す
_client = boto3.client(
    "bedrock-runtime",
    region_name=settings.aws_region,
    config=Config(
        retries={"max_attempts": 2, "mode": "standard"},
        read_timeout=30,   # Lambda のタイムアウト（30秒）と揃える
        connect_timeout=5,
    ),
)


def ask(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """これまでの会話（history）の後ろに今回の発言を足して送り、答えの文字と実測値を返す。

    history は Converse API の messages と同じ形（role と content の並び）。無ければ第5回と同じ1問1答。
    返す辞書の項目は main.py の ChatResponse に合わせてある。
    assistant_message は「モデルの今回の発言」そのもの。履歴に保存するために返す。
    """
    started = time.monotonic()

    messages = list(history or [])
    messages.append({"role": "user", "content": [{"text": message}]})

    response = _client.converse(
        modelId=settings.bedrock_model_id,
        # system は messages とは別枠で渡す。毎回その場で組み立てる（日付が入っているため）
        system=[{"text": build_system_prompt()}],
        messages=messages,
        inferenceConfig={
            "maxTokens": settings.max_tokens,
            "temperature": settings.temperature,
        },
    )

    assistant_message = response["output"]["message"]
    # content は複数のブロックで返ることがある。text のものを全部つなぐ
    text = "".join(block.get("text", "") for block in assistant_message["content"]).strip()
    usage = response.get("usage", {})

    return {
        "reply": text or "（応答が空でした）",
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "stop_reason": response.get("stopReason", ""),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "assistant_message": assistant_message,
    }
