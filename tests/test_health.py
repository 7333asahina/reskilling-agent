"""器そのもののテスト。ネットワークには一切出ない。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index_returns_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "<!doctype html>" in res.text.lower()


def test_chat_echoes_message():
    res = client.post("/api/chat", json={"message": "こんにちは"})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "受け取りました: こんにちは"
    assert body["model"]          # 画面にモデル名を出すので空にならないこと


def test_chat_rejects_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_rejects_too_long_message():
    """入力の長さに上限があること。無いと1リクエストのコストに上限が無くなる（第5回）。"""
    res = client.post("/api/chat", json={"message": "あ" * 4001})
    assert res.status_code == 422
