"""器そのもののテスト（第5回版。tests/test_health.py を丸ごと差し替える）。

**ネットワークには一切出ない。**LLM を呼ぶ ask() を、決まった答えを返す偽物に差し替えてから叩く。
本物を呼ぶテストにすると、pytest のたびに課金され、AWS に繋がらない場所では落ちる。
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def fake_ask(message: str) -> dict:
    """LLM の代わり。受け取った文をそのまま返す（第3回の echo と同じ）。"""
    return {"reply": f"偽の答え: {message}", "input_tokens": 12, "output_tokens": 12,
            "stop_reason": "end_turn", "elapsed_ms": 1}


def test_healthz_returns_ok():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index_returns_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "<!doctype html>" in res.text.lower()


def test_chat_returns_llm_reply(monkeypatch):
    # main.py は `from app.llm import ask` で読み込んでいるので、main 側の名前を差し替える
    monkeypatch.setattr("app.main.ask", fake_ask)
    res = client.post("/api/chat", json={"message": "こんにちは"})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "偽の答え: こんにちは"
    assert body["input_tokens"] == 12      # usage が画面に渡ること
    assert body["model"]                   # 画面にモデル名を出すので空にならないこと


def test_chat_rejects_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_rejects_too_long_message():
    """入力の長さに上限があること。無いと1リクエストのコストに上限が無くなる。"""
    res = client.post("/api/chat", json={"message": "あ" * 4001})
    assert res.status_code == 422
