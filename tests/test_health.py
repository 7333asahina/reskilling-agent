"""器そのもののテスト（第8回版。tests/test_health.py を丸ごと差し替える）。

**ネットワークには一切出ない。**エージェントを回す run_agent() と、DynamoDB を読む history.load() を
偽物に差し替えてから叩く。確かめているのは器：ターン数と tool の名前が画面に返ること、
tool の往復を含む会話が丸ごと保存されること。
第8回で2件増えて 11 件になる。MCP サーバーにも繋ぎにいかない（mcp_client を偽物に差し替える）。
"""

import pytest
from fastapi.testclient import TestClient

from app import history, mcp_client
from app.main import app
from app.tools import all_tool_specs, run_tool

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


def fake_run_agent(message: str, past: list | None = None) -> dict:
    """エージェントの代わり。tool を1回使って2ターンした、という体の結果を返す。"""
    n = len(past or [])
    messages = list(past or []) + [
        {"role": "user", "content": [{"text": message}]},
        {"role": "assistant", "content": [{"text": f"偽の答え: {message}（過去 {n} 件）"}]},
    ]
    return {"reply": f"偽の答え: {message}（過去 {n} 件）", "messages": messages,
            "turns": 2, "tools_used": ["get_current_time"],
            "input_tokens": 500 + n * 40, "output_tokens": 60,
            "stop_reason": "end_turn", "elapsed_ms": 1}


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


def test_chat_returns_turns_and_tools(monkeypatch):
    """ターン数と tool の名前が画面に返ること。第6回まで turns は 1 固定だった。"""
    monkeypatch.setattr("app.main.run_agent", fake_run_agent)
    monkeypatch.setattr(history, "load", lambda session_id, user_id=history.ANONYMOUS: [])
    monkeypatch.setattr(history, "save", lambda session_id, messages, user_id=history.ANONYMOUS: None)
    res = client.post("/api/chat", json={"message": "いま何時？"})
    assert res.status_code == 200
    body = res.json()
    assert body["turns"] == 2
    assert body["tools_used"] == ["get_current_time"]
    assert body["history_messages"] == 0


def test_chat_saves_whole_conversation(monkeypatch):
    """ tool の往復を含む会話が丸ごと保存されること。DynamoDB は呼ばない。"""
    saved = {}
    monkeypatch.setattr("app.main.run_agent", fake_run_agent)
    monkeypatch.setattr(history, "load", lambda session_id, user_id=history.ANONYMOUS: [_u("前の質問"), _a("前の答え")])
    monkeypatch.setattr(history, "save", lambda session_id, messages, user_id=history.ANONYMOUS: saved.update({"messages": messages}))

    res = client.post("/api/chat", json={"message": "続きの質問", "session_id": "abc"})
    assert res.status_code == 200
    assert res.json()["history_messages"] == 2
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant", "user", "assistant"]


def test_run_tool_returns_result():
    """ tool が動くこと。ここだけはネットワークに出ないので本物を呼ぶ。"""
    result = run_tool("get_current_time", {"timezone": "JST"})
    assert result["timezone"] == "JST"
    assert "年" in result["readable"]


def test_trim_keeps_latest_and_starts_with_user():
    msgs = [_u("q1"), _a("a1"), _u("q2"), _a("a2"), _u("q3"), _a("a3")]
    assert history.trim(msgs, 4) == msgs[-4:]
    assert history.trim(msgs, 3)[0]["role"] == "user"
    assert len(history.trim(msgs, 3)) == 2
    assert history.trim(msgs, 20) == msgs


def test_chat_rejects_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_rejects_too_long_message():
    res = client.post("/api/chat", json={"message": "あ" * 4001})
    assert res.status_code == 422


def test_run_tool_does_not_raise_on_failure():
    """ tool が失敗しても例外を外に出さず、error を結果として返すこと。

    例外が外に出ると、tool が1つ壊れただけで会話全体が HTTP 500 で落ちる（4-1 で見たもの）。
    error を返せば、モデルはそれを読んで謝るか、別の言い方を試せる。
    """
    assert "error" in run_tool("get_current_time", {"timezone": 999})   # 引数が変
    assert "error" in run_tool("get_weather", {})                       # 無い tool


# ---------- 第8回で増えたもの ----------

def test_mcp_tools_are_added_to_local_ones(monkeypatch):
    """MCP サーバーの一覧が、手元の一覧の後ろに足されること。

    モデルに渡る toolConfig は1つの配列で、手元のものと MCP のものが並んでいる。
    **モデルの側にはどちらがどちらか分からない。**振り分けるのは agent.py の仕事。
    """
    fake = [
        {"toolSpec": {"name": "search_mail", "description": "Gmail を検索する",
                      "inputSchema": {"json": {"type": "object", "properties": {}}}}},
        {"toolSpec": {"name": "list_events", "description": "カレンダーの予定を返す",
                      "inputSchema": {"json": {"type": "object", "properties": {}}}}},
    ]
    monkeypatch.setattr(mcp_client, "list_tools", lambda: fake)
    names = [t["toolSpec"]["name"] for t in all_tool_specs() + mcp_client.list_tools()]
    assert names == ["get_current_time", "search_mail", "list_events"]


def test_mcp_failure_does_not_break_local_tools(monkeypatch):
    """MCP サーバーに繋がらなくても、手元の tool は使えること。

    繋がらなかった1台のために、時刻を聞くだけの用事まで止める理由はない。
    """
    monkeypatch.setattr(mcp_client, "list_tools", lambda: [])
    assert [t["toolSpec"]["name"] for t in all_tool_specs()] == ["get_current_time"]
    assert run_tool("get_current_time", {"timezone": "JST"})["timezone"] == "JST"
