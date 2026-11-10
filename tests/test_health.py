"""器そのもののテスト（第6回版。tests/test_health.py を丸ごと差し替える）。

**ネットワークには一切出ない。**LLM を呼ぶ ask() と、DynamoDB を読む history.load() を偽物に差し替えてから叩く。
確かめているのは器：過去の発言が ask() に渡ること、その数が画面に返ること、上限で古いものが落ちること。
"""

import pytest
from fastapi.testclient import TestClient

from app import history
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_dynamodb(monkeypatch):
    """どのテストも DynamoDB に読み書きしない。

    .env に CONVERSATION_TABLE が入っていると、history.load() は本物の表を読む。
    放っておくとテストを回すたびに session "default" の履歴が積み上がり、
    history_messages が 0 でなくなる。
    履歴の中身が要るテストは、この上からもう一度差し替える。
    """
    monkeypatch.setattr(history, "load", lambda session_id, user_id=history.ANONYMOUS: [])
    monkeypatch.setattr(history, "save", lambda session_id, messages, user_id=history.ANONYMOUS: None)


def fake_ask(message: str, past: list | None = None) -> dict:
    """LLM の代わり。受け取った文と、渡された過去の発言の数を返す。"""
    n = len(past or [])
    return {"reply": f"偽の答え: {message}（過去 {n} 件）", "input_tokens": 12 + n * 40, "output_tokens": 12,
            "stop_reason": "end_turn", "elapsed_ms": 1,
            "assistant_message": {"role": "assistant", "content": [{"text": f"偽の答え: {message}"}]}}


def _u(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


def _a(text: str) -> dict:
    return {"role": "assistant", "content": [{"text": text}]}


def test_healthz_returns_ok():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index_returns_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "<!doctype html>" in res.text.lower()


def test_chat_returns_llm_reply(monkeypatch):
    monkeypatch.setattr("app.main.ask", fake_ask)
    res = client.post("/api/chat", json={"message": "こんにちは"})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "偽の答え: こんにちは（過去 0 件）"   # CONVERSATION_TABLE が空 ＝ 履歴なし
    assert body["input_tokens"] == 12
    assert body["history_messages"] == 0


def test_chat_sends_history_to_llm(monkeypatch):
    """履歴があれば ask() に渡り、その数が画面に返ること。DynamoDB は呼ばない（load を偽物にする）。"""
    saved = {}
    monkeypatch.setattr("app.main.ask", fake_ask)
    monkeypatch.setattr(history, "load", lambda session_id, user_id=history.ANONYMOUS: [_u("前の質問"), _a("前の答え")])
    monkeypatch.setattr(history, "save", lambda session_id, messages, user_id=history.ANONYMOUS: saved.update({"messages": messages}))

    res = client.post("/api/chat", json={"message": "続きの質問", "session_id": "abc"})
    assert res.status_code == 200
    body = res.json()
    assert body["history_messages"] == 2
    assert body["reply"] == "偽の答え: 続きの質問（過去 2 件）"
    # 保存されるのは「前の2件 ＋ 今回の発言 ＋ 今回の答え」の4件
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant", "user", "assistant"]


def test_trim_keeps_latest_and_starts_with_user():
    """上限を超えたら古いものから落ち、先頭が user から始まること。"""
    msgs = [_u("q1"), _a("a1"), _u("q2"), _a("a2"), _u("q3"), _a("a3")]
    assert history.trim(msgs, 4) == msgs[-4:]
    assert history.trim(msgs, 3)[0]["role"] == "user"      # 3件なら a2 が先頭になるので落として2件
    assert len(history.trim(msgs, 3)) == 2
    assert history.trim(msgs, 20) == msgs                   # 上限内ならそのまま


def test_chat_rejects_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_rejects_too_long_message():
    """入力の長さに上限があること。無いと1リクエストのコストに上限が無くなる。"""
    res = client.post("/api/chat", json={"message": "あ" * 4001})
    assert res.status_code == 422
