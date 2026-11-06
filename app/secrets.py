"""鍵の読み方（第4回。app/secrets.py として新しく置く）。

鍵の置き場所は2つある。

    手元   .env の DEMO_API_KEY            → settings.demo_api_key に入る
    AWS    Secrets Manager の 1件           → settings.demo_api_key_secret_name の名前で読む

どちらから来たかを、使う側（main.py）は気にしなくてよい。この関数が吸収する。

**読めなくても例外を外に出さない。**/healthz がここで落ちると、Lambda Web Adapter が
「起動失敗」と判断してアプリ全体が動かなくなる。鍵が無いのは「鍵が無い」という状態であって、
アプリが死ぬ理由ではない。
"""

import logging
from functools import lru_cache

import boto3

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def demo_api_key() -> str:
    """鍵の値を返す。無ければ空文字。**この値をログや画面に出さないこと。**"""
    if settings.demo_api_key:
        return settings.demo_api_key

    if not settings.demo_api_key_secret_name:
        return ""

    try:
        sm = boto3.client("secretsmanager", region_name=settings.aws_region)
        value = sm.get_secret_value(SecretId=settings.demo_api_key_secret_name)["SecretString"]
        # 読めたことは残す。値は残さない
        logger.info("secret loaded", extra={"extra_fields": {"secret_name": settings.demo_api_key_secret_name}})
        return value
    except Exception:  # noqa: BLE001  鍵が読めなくてもアプリは動かす
        logger.warning("secret not available", extra={"extra_fields": {"secret_name": settings.demo_api_key_secret_name}})
        return ""
