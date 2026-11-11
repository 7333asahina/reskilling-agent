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

from botocore.exceptions import ClientError

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.auth import current_user
from app.config import settings
from app.logging_conf import setup_logging
from app.secrets import demo_api_key
from app.agent import run_agent

from app import history


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
    """生きているかの確認用。第4回から AWS がここを叩く。200 を返さないと起動失敗になる。"""
    return {
        "status": "ok",
        "env": settings.app_env,
        "student_id": settings.student_id,
        "app_name": settings.app_name,
        "api_key_set": bool(demo_api_key()),
    }


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
    """これまでの会話を読み、エージェントを回して答えを返し、会話を保存する。"""
    logger.info("chat request received", extra={"extra_fields": {
        "chars": len(req.message), "session_id": req.session_id, "user": user.get("sub", "")}})

    # 1. 読む。CONVERSATION_TABLE が空なら [] が返る
    past = history.load(req.session_id)

    # 2. 回す。1ターンで終わることも、tool を使って2ターンすることもある
    try:
        result = run_agent(req.message, past)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.exception("bedrock call failed", extra={"extra_fields": {"error_code": code}})
        if code == "ThrottlingException":
            raise HTTPException(status_code=429, detail="混み合っています。少し待って再送してください") from e
        raise HTTPException(status_code=502, detail=f"モデルの呼び出しに失敗しました（{code}）") from e

    # 3. 保存する。**tool の往復（toolUse・toolResult）も含めて丸ごと残す。**
    #    run_agent が返す messages は、これまでの会話＋今回の往復の全部になっている
    history.save(req.session_id, result["messages"])

    logger.info("chat request completed", extra={"extra_fields": {
        "turns": result["turns"],
        "tools_used": result["tools_used"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "stop_reason": result["stop_reason"],
        "elapsed_ms": result["elapsed_ms"],
        "history_messages": len(past),
    }})

    return ChatResponse(
        reply=result["reply"],
        turns=result["turns"],
        tools_used=result["tools_used"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        elapsed_ms=result["elapsed_ms"],
        model=settings.bedrock_model_id,
        history_messages=len(past),
    )


@app.get("/api/suggestions")
def suggestions() -> list[str]:
    """画面の定型質問ボタン。ここを変えると、画面のボタンが変わる（3-2 で画面側をつなぐ）。"""
    return [
        "今週の予定を教えて",
        "今日は何曜日？",
        "生成AIのRAGとは何か、3行で説明して",
        "議事録のテンプレートを作って",
    ]
