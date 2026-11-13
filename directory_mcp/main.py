"""社内名簿のMCPサーバー。**第4章（第8〜9回）で受講者が自分で作るお手本。**

MCPの正体は **JSON-RPC 2.0**。対応するメソッドは3つだけ。

    initialize   … 挨拶。「私はこういうサーバーです」と名乗る
    tools/list   … 「どんな tool がありますか」に答える
    tools/call   … 「この tool をこの引数で使ってください」を実行する

エージェント側は tools/list で一覧を受け取り、そのまま Bedrock に渡す。
**エージェントのコードには search_people の文字列が1度も出てこない。**
繋ぎ先のURLを1行足すだけで tool が2つ増える。それがMCPを挟む理由。

## 「別サーバー」とはどこまでのことか

このMCPサーバーは、**エージェント本体と同じコンテナの中で、別プロセスとして動く。**

    コンテナ ┬ uvicorn :8080  エージェント本体（外に公開される）
            └ uvicorn :8081  これ（127.0.0.1 にだけ縛る。外から到達できない）

AWSのリソースは1つも増えない。それでもMCPとしては何も欠けていない。
**MCPは「tool の渡し方の規格」であって、どこに置くかとは別の話**だから（D-25 軸①）。

Gmail・カレンダーのMCP（`mcp-server/`）は、対照的に**本当に別のLambda**にしてある。
理由は「Googleの鍵をエージェント本体に持たせたくない」——置き場所の判断は
**探し方でも規模でもなく、権限を分けたいかどうかで決まる**（D-27）。

    こちら（名簿）  … AWSの権限を1つも持たない。分ける理由が無いので同居させる
    あちら（Gmail） … Secrets Manager を読む。分ける理由があるので別Lambdaにする

## 外に出さないこと

**パスで生やしてはいけない。**本体の関数URLは認証が NONE なので、
`/directory/mcp` のように同じポートに生やすと、名簿が認証なしで全世界に公開される。
ポートを分け、`--host 127.0.0.1` で縛る。これがこのファイルの一番の勘所。
"""

import json
import logging
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from directory_mcp.logging_conf import STUDENT_ID, setup_logging
from directory_mcp.people import BY_ID, PEOPLE

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="社内名簿 MCP サーバー", version="0.1.0")

PROTOCOL_VERSION = "2025-06-18"

# 返す件数の上限。**モデルには渡さない。**
# 件数を引数にすると、モデルが limit=1 を渡して外れの1件で答えを作る（D-23の実測）
MAX_RESULTS = 10


# ---------- ツール定義 ----------
# description はモデルが「どの tool をいつ使うか」を決める唯一の手がかり。
# 「いつ使うか」と「いつ使わないか」の両方を書く（Nova Liteは書かないと呼びすぎる。D-12）

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_people",
        "description": (
            "社員名簿を検索して、該当する社員を返す。"
            "名前・ふりがな・部署名・役職のいずれかに、渡した文字が含まれる社員を探す。"
            "「営業部の部長は誰」「田中さんの内線は」「山本さんは何部」など、"
            "**社内の人**について聞かれたときに使う。"
            "**氏名・部署・役職・内線番号・メールアドレスをすべて返すので、この1回で答えられる。**"
            "該当が無ければ0件を返す。0件なら「該当する社員はいません」と答えること。"
            "社内規程や制度の内容を調べる用途には使わない。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "**氏名・部署名・役職名だけ**を入れる。例: 田中 / 営業部 / 経営企画部の部長。"
                        "「内線」「番号」「メール」「教えて」のような、"
                        "**探している項目を表す語は入れないこと。**入れると0件になる"
                    ),
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_person",
        "description": (
            "社員IDを指定して、その1名だけを返す。"
            "**社員IDが分かっているときにしか使えない。**"
            "名前・部署・役職から探すときは search_people を使うこと。"
            "search_people はすでに内線番号もメールアドレスも返すので、"
            "そのあとにこのツールを呼ぶ必要はない。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string", "description": "社員ID。例: E008。氏名ではない"},
            },
            "required": ["person_id"],
        },
    },
]


# ---------- tool の中身 ----------

# 照合するときに見る欄
FIELDS = ("name", "kana", "dept", "title")

# 検索語を区切る文字。**「の」も区切りにする。**
# モデルは「経営企画部の部長」のように、部署と役職をつなげて渡してくる（実測）。
# つなげたままだと、どの欄にも一致せず0件になり、「いません」と答えてしまう
_SPLIT = re.compile(r"[\s\u3000のと、,・/]+")

# 末尾の敬称は落とす。「田中さん」で引けないと使い物にならない
_HONORIFIC = re.compile(r"(さん|様|氏|くん|君|さま)$")


def _norm(text: str) -> str:
    """比べる前に空白を落とす。「営業部 第1課」と「営業部第1課」を同じ扱いにする。"""
    return text.replace(" ", "").replace("\u3000", "")


def _terms(keyword: str) -> list[str]:
    """検索語を、照合できる単位に割る。

        「経営企画部の部長」 → ["経営企画部", "部長"]
        「田中 健一」        → ["田中", "健一"]
        「田中さん」          → ["田中"]
    """
    parts = (_HONORIFIC.sub("", t.strip()) for t in _SPLIT.split(keyword))
    return [t for t in parts if t]


def search_people(keyword: str) -> dict[str, Any]:
    """名前・ふりがな・部署・役職を**文字で**照合する。意味では探さない。

    ここが RAG（意味で探す）との決定的な違い。
    該当が無ければ **0件を返せる。**「該当する社員はいません」と言い切れる。
    ベクトル検索は必ず一番近いものを返すので、これができない（D-25）。
    """
    terms = _terms(keyword)
    # **すべての語が当たった人だけを返す（AND）。**
    # どれか1つでも当たれば返す形（OR）にすると、「人事部の鈴木さん」で
    # 人事部の全員が返る。**いない人を「いない」と言えなくなる**のがいちばん困る
    hits = [
        p for p in PEOPLE
        if terms and all(any(t in _norm(p[f]) for f in FIELDS) for t in terms)
    ]
    return {
        "count": len(hits),
        # **1件ぶんを丸ごと返す。** 連絡先を伏せて get_person に取りに来させる形にしたら、
        # モデルが2段目を呼ばずに、手元にある社員IDを内線番号として答えた（P9の実測）。
        #
        #   質問「営業部の田中部長の内線番号を教えて」
        #   tool search_people ×3（get_person に進まない）
        #   返答「営業部の田中部長の内線番号は、E008です」  ← 社員IDを内線と言った
        #
        # メールの本文と違って、名簿の1行は短い。伏せて得るものが無く、
        # **2段にしたぶんだけ間違える余地を作っていた**（D-23と同じ筋）
        "people": [dict(p, person_id=p["id"]) for p in hits[:MAX_RESULTS]],
        "truncated": len(hits) > MAX_RESULTS,
    }


def get_person(person_id: str) -> dict[str, Any]:
    person = BY_ID.get(person_id.strip().upper())
    if person is None:
        return {"found": False, "message": f"社員ID {person_id} は名簿にありません"}
    return {"found": True, "person": dict(person, person_id=person["id"])}


HANDLERS = {
    "search_people": lambda a: search_people(a["keyword"]),
    "get_person": lambda a: get_person(a["person_id"]),
}

# ログに出してよい引数だけを通す（許可リスト方式）。禁止リストにすると書き漏れて漏れる。
#
#   keyword    … **出さない。** 利用者が打った文字そのもの。
#                「誰を探したか」が CloudWatch Logs に残る
#   person_id  … 出す。こちらが発行した社内の管理番号で、名簿を持つ人にしか意味がない。
#                どの tool がどう呼ばれたかを後から追えないと、障害のとき手が出せなくなる
#
# **この差の理由を説明できることが、第9回PM「責任分界とログ設計」の到達点。**
LOGGABLE_ARGS: dict[str, set[str]] = {
    "search_people": set(),
    "get_person": {"person_id"},
}


def _loggable(name: str, args: dict[str, Any]) -> dict[str, Any]:
    allowed = LOGGABLE_ARGS.get(name, set())
    return {k: (v if k in allowed else "***") for k, v in args.items()}


# ---------- JSON-RPC の入口 ----------

class RpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = {}


def _ok(rid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "tools": len(TOOLS), "people": len(PEOPLE)}


@app.post("/mcp")
def rpc(req: RpcRequest) -> dict[str, Any]:
    """MCPの入口。JSON-RPCを1件処理する。"""

    if req.method == "initialize":
        return _ok(req.id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": f"{STUDENT_ID}-directory-mcp", "version": "0.1.0"},
        })

    if req.method in ("notifications/initialized", "ping"):
        return _ok(req.id, {})

    if req.method == "tools/list":
        return _ok(req.id, {"tools": TOOLS})

    if req.method == "tools/call":
        name = req.params.get("name", "")
        args = req.params.get("arguments", {}) or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return _err(req.id, -32602, f"'{name}' という tool はありません")

        logger.info("tool called", extra={"extra_fields": {"tool": name, "args": _loggable(name, args)}})

        try:
            result = handler(args)
        except KeyError as e:
            return _err(req.id, -32602, f"引数 {e} が足りません")
        except Exception:
            # tool の失敗で会話を止めない。失敗したという事実を結果として返す
            logger.exception("tool failed", extra={"extra_fields": {"tool": name}})
            return _ok(req.id, {"content": [{"type": "text", "text": "tool の実行に失敗しました"}],
                                "isError": True})

        logger.info("tool finished", extra={"extra_fields": {"tool": name, "count": result.get("count")}})
        # MCPは結果を content の配列で返す決まり。JSONは文字列にして入れる
        return _ok(req.id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "isError": False,
        })

    return _err(req.id, -32601, f"未対応のメソッドです: {req.method}")
