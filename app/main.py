"""アプリの入り口。

FastAPI のふつうのウェブアプリ。第4回で Docker に入れて AWS Lambda に載せるが、
コードのどこにも Lambda は出てこない（Dockerfile を見ること）。

第3回時点：/api/chat は「受け取った文字をそのまま返す」だけ。
ただし返す形（reply・turns・tokens …）は完成形と同じにしてある。
第5回でこの関数の中身を LLM（Amazon Bedrock）の呼び出しに差し替えても、画面側は変えなくてよい。
"""

import logging
import time
from pathlib import Path

from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.auth import current_user
from app.config import settings
from app.logging_conf import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")

WEB_DIR = Path(__file__).parent / "web"


# ---------- リクエストとレスポンスの型 ----------
# 型を先に書いておくと、FastAPI が入力の検証と /docs の画面を自動で作ってくれる。

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="利用者からの入力")
    # どの会話の続きかを示す。ブラウザが作って送ってくる（第6回で履歴に使う）
    session_id: str = Field(default="default", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ChatResponse(BaseModel):
    reply: str
    # 画面に実測値を出す。第5回から本物の数字が入る。いまは 0
    turns: int = 0
    tools_used: list[str] = []
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed_ms: int = 0
    model: str = "echo"
    history_messages: int = 0


# ---------- エンドポイント ----------

@app.get("/healthz")
def healthz() -> dict:
    """生きているかの確認用。第4回で AWS がここを叩く。200 を返さないと起動失敗になる。"""
    return {"status": "ok", "env": settings.app_env, "student_id": settings.student_id}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """画面を返す。ただし**手元で動かしているときだけ。**

    第4回で AWS に載せると、画面は S3 に置いて CloudFront から配るようになる
    （deploy_web.py が置く）。Lambda が返すのは API だけになり、
    画面を見るだけの人が Lambda を起こさなくなる。コールドスタートも課金も減る。

    間違ってこちらを開いた人が迷わないよう、案内だけ返しておく。
    """
    if settings.app_env == "local":
        return (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return (
        "<!doctype html><html lang='ja'><meta charset='utf-8'>"
        "<title>API の入口</title>"
        "<body style='font-family:system-ui,sans-serif;max-width:36em;margin:15vh auto;"
        "padding:0 1.5em;line-height:1.8;color:#333'>"
        "<h1 style='font-size:1.1rem'>ここは API の入口です</h1>"
        "<p>画面は CloudFront から配られています。"
        "スタックの出力 <code>WebUrl</code> の URL を開いてください。</p>"
        "<p style='color:#777;font-size:.9em'>"
        "<code>GET /healthz</code> ／ <code>POST /api/chat</code>（要ログイン）</p>"
        "</body></html>"
    )


@app.get("/config.json", include_in_schema=False)
def config() -> dict:
    """画面が「いま手元か、AWS か」を見分けるための設定。

    **手元には設定が無いので、空を返す。**画面は空を受け取るとローカルと判断し、
    ログインを求めない。第4回で AWS に載せると、この設定は S3 に置かれて
    CloudFront から配られる（deploy_web.py が書き出す）ので、ここは通らない。

    空でも 200 を返すのが肝。404 にすると、ブラウザのコンソールに赤い行が残る。
    """
    return {}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict[str, Any] = Depends(current_user)) -> ChatResponse:
    """第3回時点では、受け取った文字をそのまま返す。

    第5回で、この中身を Bedrock の呼び出しに差し替える。
    受け取る形・返す形・記録する、の3つを先に作っておくのがこの回の目的。

    **Depends(current_user) が先に動く。**ログインしていなければ 401 でここまで来ない。
    手元（app_env が local）では require_auth が False なので素通しする。
    """
    started = time.monotonic()
    logger.info("chat request received", extra={"extra_fields": {
        "chars": len(req.message), "session_id": req.session_id, "user": user.get("sub", "")}})
    reply = f"受け取りました: {req.message}"
    return ChatResponse(reply=reply, elapsed_ms=int((time.monotonic() - started) * 1000))
