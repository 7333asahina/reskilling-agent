"""MCP サーバーに JSON-RPC を送る部分（第8回。app/mcp_client.py として新しく置く）。

**このファイルに `search_mail` も `list_events` も出てきません。**
起動のあとで `tools/list` を送り、返ってきたツール定義をそのまま Bedrock に渡します。
MCP サーバー側に tool が増えても、こちらは1行も直りません。

## 繋ぎ先は1本とは限らない

`MCP_URLS` はカンマ区切りです。第8回は1本。

    https://xxxx.lambda-url.ap-northeast-1.on.aws/   Gmail・カレンダー

第9回で自分の書いた MCP サーバーを2本目に足しますが、そのとき変えるのは `.env` の1行だけで、
このファイルは変わりません。

## 名前から接続先を引く表

`tools/call` をどこに送るかは、`tools/list` の答えから自動で作ります。
どの tool がどのサーバーのものかを、こちらで書き並べる必要はありません。

## 署名

`AWS_IAM` 認証の関数 URL は、AWS の署名（SigV4）が付いていないと 403 を返します。
`127.0.0.1` は AWS のサービスではないので署名しません（第9回で繋ぐ相手がこれです）。
"""

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from app.config import settings

logger = logging.getLogger(__name__)

_session = boto3.Session()

# ツール定義の一覧（Bedrock に渡す形）と、「tool の名前 → どの接続先が持っているか」の表。
# 2つセットで作り、2つセットで捨てる
_tools_cache: list[dict[str, Any]] | None = None
_route: dict[str, str] = {}
_cached_at: float = 0.0

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def servers() -> list[str]:
    """接続先の一覧。カンマ区切りの設定を、末尾のスラッシュを落として並べる。"""
    return [u.strip().rstrip("/") for u in settings.mcp_urls.split(",") if u.strip()]


def needs_signature(url: str) -> bool:
    """AWS の署名を付ける相手か。関数 URL には要る。127.0.0.1 には要らない。"""
    return urlparse(url).hostname not in _LOCAL_HOSTS


def _rpc(base_url: str, method: str, params: dict[str, Any] | None = None,
         timeout: int = 25) -> dict[str, Any]:
    """JSON-RPC を1件送って、result の中身を返す。"""
    url = base_url.rstrip("/") + "/mcp"
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    if needs_signature(url):
        creds = _session.get_credentials()
        if creds is None:
            # aws configure をしていないと、ここで None が返る。
            # そのまま進めると 'NoneType' object has no attribute ... という
            # 何の話か分からない例外になるので、ここで止めて理由を書く（T-104）
            raise RuntimeError(
                "AWS の資格情報が見つかりません。aws configure を実行してください"
            )
        req = AWSRequest(method="POST", url=url, data=body, headers=dict(headers))
        SigV4Auth(creds.get_frozen_credentials(), "lambda", settings.aws_region).add_auth(req)
        headers = dict(req.headers)

    try:
        with urlopen(Request(url, data=body, headers=headers, method="POST"), timeout=timeout) as res:
            payload = json.load(res)
    except HTTPError as e:
        raise RuntimeError(
            f"MCP サーバーが HTTP {e.code} を返しました: "
            f"{e.read().decode('utf-8', 'replace')[:200]}"
        ) from e
    except URLError as e:
        raise RuntimeError(f"MCP サーバーに繋がりません: {e.reason}") from e

    if "error" in payload:
        raise RuntimeError(f"MCP サーバーがエラーを返しました: {payload['error']}")
    return payload.get("result", {})


def list_tools() -> list[dict[str, Any]]:
    """接続先すべてに tools/list を送り、Bedrock に渡す形にして返す。

    毎回送ると1往復ぶん遅くなるので、MCP_CACHE_SECONDS のあいだは前の答えを使う。
    **1台が落ちていても、残りの接続先と手元の tool はそのまま使える。**
    """
    global _tools_cache, _route, _cached_at

    urls = servers()
    if not urls:
        return []
    if _tools_cache is not None and time.time() - _cached_at < settings.mcp_cache_seconds:
        return _tools_cache

    specs: list[dict[str, Any]] = []
    route: dict[str, str] = {}
    reached = 0

    for base in urls:
        try:
            result = _rpc(base, "tools/list", timeout=10)
        except Exception:
            logger.exception("mcp tools/list failed; skipping this server",
                             extra={"extra_fields": {"server": base}})
            continue

        reached += 1
        for t in result.get("tools", []):
            name = t["name"]
            if name in route:
                # 同じ名前の tool を2台が公開している。モデルには区別が付かないので、
                # 黙って上書きせず、先に見つかったほうを使って警告を残す
                logger.warning("duplicate mcp tool name; keeping the first one",
                               extra={"extra_fields": {"tool": name, "server": base}})
                continue
            route[name] = base
            # MCP の inputSchema と Bedrock の inputSchema.json は中身が同じ形。
            # 包み方だけ違うので、そこを合わせる
            specs.append({"toolSpec": {
                "name": name,
                "description": t.get("description", ""),
                "inputSchema": {"json": t.get("inputSchema", {"type": "object", "properties": {}})},
            }})

    if reached == 0:
        # 1台も応答しなかった。前の一覧が残っていればそれを使う（tool の名前は変わらないため）
        return _tools_cache or []

    _tools_cache, _route, _cached_at = specs, route, time.time()
    logger.info("mcp tools loaded", extra={"extra_fields": {
        "servers": len(urls), "reached": reached, "count": len(specs), "names": list(route),
    }})
    return specs


def has(name: str) -> bool:
    """その名前の tool を、接続先のどれかが持っているか。"""
    list_tools()
    return name in _route


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """MCP サーバーの tool を1つ動かす。返すのは辞書（そのまま toolResult の中身になる）。"""
    list_tools()
    base = _route.get(name)
    if base is None:
        return {"error": f"{name} という tool を持つ MCP サーバーがありません"}

    logger.info("mcp tool call", extra={"extra_fields": {"tool": name, "server": base}})
    try:
        result = _rpc(base, "tools/call", {"name": name, "arguments": args})
    except RuntimeError as e:
        # **ここで握る。**MCP サーバーが落ちていても会話は続く（第7回 run_tool と同じ考え方）
        logger.exception("mcp tool call failed", extra={"extra_fields": {"tool": name}})
        return {"error": str(e)}

    texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    raw = "\n".join(texts)

    if result.get("isError"):
        return {"error": raw or "tool の実行に失敗しました"}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON で返ってこない tool もありうる。そのときは文字列のまま渡す
        return {"text": raw}
