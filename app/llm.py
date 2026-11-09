"""LLM を1回呼ぶ（第5回。app/llm.py として新しく置く）。

第5回は1問1答。前の会話は渡さない（第6回）。役割の指示も渡さない（第6回）。tool も渡さない（第6回〜第7回）。
**送るものと返るものは、午前に CLI で見たものと同じ。**呼ぶ場所が Python に変わっただけ。
"""

import logging
import time
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings

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


def ask(message: str) -> dict[str, Any]:
    """利用者の1文を送り、答えの文字と実測値を返す。

    返す辞書の項目は main.py の ChatResponse に合わせてある。
    """
    started = time.monotonic()

    response = _client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": message}]}],
        inferenceConfig={
            "maxTokens": settings.max_tokens,
            "temperature": settings.temperature,
        },
    )

    # content は複数のブロックで返ることがある。text のものを全部つなぐ
    text = "".join(
        block.get("text", "") for block in response["output"]["message"]["content"]
    ).strip()
    usage = response.get("usage", {})

    return {
        "reply": text or "（応答が空でした）",
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "stop_reason": response.get("stopReason", ""),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
