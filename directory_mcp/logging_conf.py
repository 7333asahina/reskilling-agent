"""ログの出し方。**エージェント本体とは別プロセスなので、自前で持つ。**

`app/logging_conf.py` とほぼ同じ内容だが、あちらを import していない。
MCPサーバーは「独立して動くもの」なので、本体の設定に依存させない。
このフォルダだけを持ち出しても、そのまま別のマシンで動く。

標準出力に1行1件のJSONで出す。同じコンテナで動いているので、
本体のログと混ざって CloudWatch Logs に届く。**混ざるからこそ `source` を入れる。**
これが無いと、どちらが出したログか後から分けられない。
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

STUDENT_ID = os.environ.get("STUDENT_ID", "s00")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "student_id": STUDENT_ID,
            # 本体のログと同じ場所に出るので、出どころを必ず名乗る
            "source": "directory-mcp",
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(LOG_LEVEL.upper())
