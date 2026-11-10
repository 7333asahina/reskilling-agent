"""会話の履歴を DynamoDB に置く（第6回。app/history.py として新しく置く）。

モデルは前の発言を覚えていない。文脈が続いているように見えるのは、
**毎回これまでの会話を全部 messages に積んで送り直している**から（第6回 03 の 2-1 で CLI で手で書いたこと）。

だから履歴はアプリ側で持つ。Lambda は1回ごとに使い捨てられるので、関数の中の変数に置いても
次のリクエストでは消えている。外（DynamoDB）に置く。

置き方：
    パーティションキー = user_id     第6回は全員 "anonymous"。第14回でログインした人の ID になる
    ソートキー         = session_id  ブラウザが作って /api/chat に送ってくる（第3回から入っている）
    messages           = Converse API の messages をそのまま JSON 文字列で
    expires_at         = この時刻を過ぎたら AWS が消す（TTL）

呼び出し側（main.py）は load と save だけ知っていればよい。上限も切り方もこのファイルに閉じてある。
"""

import json
import logging
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# 第6回はログインが無いので、全員この ID。第14回で Cognito の sub に置き換わる
ANONYMOUS = "anonymous"

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource(
            "dynamodb",
            region_name=settings.aws_region,
            config=Config(retries={"max_attempts": 2, "mode": "standard"}, read_timeout=5),
        ).Table(settings.conversation_table)
    return _table


def trim(messages: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    """古い発言を捨てて、送る量に上限をかける。

    **上限が無いと、会話が続くほど毎回の inputTokens が増え続ける。**料金は入力トークンで決まるので、
    長い会話ほど1問あたりが高くなる。

    切り方は「後ろから max_messages 件」。ただし Converse API は messages が user から始まり、
    user と assistant が交互でないと弾くので、先頭が assistant になったらそれも落とす。
    （tool の往復が入ると切り方がもう1段むずかしくなる。第12回）
    """
    cut = messages[-max_messages:] if len(messages) > max_messages else list(messages)
    while cut and cut[0].get("role") != "user":
        cut.pop(0)

    dropped = len(messages) - len(cut)
    if dropped:
        # **忘れたことを見えるようにしておく。**
        # 上限に達したことが分からないと「急に前の話を忘れた」の原因が追えない
        logger.info("history trimmed", extra={"extra_fields": {
            "before": len(messages), "after": len(cut), "max": max_messages,
        }})
    return cut


def load(session_id: str, user_id: str = ANONYMOUS) -> list[dict[str, Any]]:
    """これまでの会話を読む。無ければ空。読んだ時点で切り詰める。

    履歴が読めなくても会話は始められる。ここで落とすと、DynamoDB が一時的に不調なだけで全員が使えなくなる。
    """
    if not settings.conversation_table:
        return []
    try:
        res = _get_table().get_item(Key={"user_id": user_id, "session_id": session_id})
    except ClientError:
        logger.exception("failed to load history")
        return []

    item = res.get("Item")
    if not item:
        return []
    try:
        stored = json.loads(item["messages"])
    except (KeyError, json.JSONDecodeError):
        logger.warning("stored history is broken; starting fresh")
        return []
    return trim(stored, settings.max_history_messages)


def save(session_id: str, messages: list[dict[str, Any]], user_id: str = ANONYMOUS) -> None:
    """会話を保存する。保存する前にも切り詰める（1項目が会話のたびに膨らみ続けないように）。

    保存の失敗で返答を失わない。返答はもう手元にあるので、履歴が残らないことより、
    利用者に答えが届かないことのほうが困る。
    """
    if not settings.conversation_table:
        return
    now = int(time.time())
    try:
        _get_table().put_item(Item={
            "user_id": user_id,
            "session_id": session_id,
            "messages": json.dumps(trim(messages, settings.max_history_messages), ensure_ascii=False),
            "updated_at": now,
            # 自動で消えるようにしておく。会話履歴を無期限に貯めない
            "expires_at": now + settings.history_ttl_days * 86400,
        })
    except ClientError:
        logger.exception("failed to save history")


def clear(session_id: str, user_id: str = ANONYMOUS) -> None:
    """この会話を消す（画面の「新しい会話」用。第6回では使わない）。"""
    if not settings.conversation_table:
        return
    try:
        _get_table().delete_item(Key={"user_id": user_id, "session_id": session_id})
    except ClientError:
        logger.exception("failed to clear history")
