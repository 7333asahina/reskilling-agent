"""エージェントが使える tool を置く場所（第7回。app/tools.py として新しく置く）。

第6回に CLI へ渡した tool-config.json の中身が、ここの description と input_schema。
違うのは、**実際に動く関数がここにあること**。モデルに渡すのはツール定義だけで、関数は渡さない。

**1つの tool について書く場所は、このファイルの TOOLS の1か所だけ。**
ツール定義と動く関数を離して書くと、tool を1つ足すのに2か所を直すことになり、
どちらかを書き忘れたときに「ツール定義はあるのに動かない」 tool ができる。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9), "JST")
UTC = timezone.utc


@dataclass(frozen=True)
class Tool:
    """ tool 1つぶん。

    name / description / input_schema … モデルに渡すツール定義（第6回の toolSpec と同じ3つ）
    run                               … 実際に動く Python の関数
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[..., dict[str, Any]]

    def spec(self) -> dict[str, Any]:
        """Converse API に渡す形（toolSpec）にする。tool-config.json と同じ形が出来上がる。"""
        return {"toolSpec": {
            "name": self.name,
            "description": self.description,
            "inputSchema": {"json": self.input_schema},
        }}


# ---------- tool の中身（実際に動く関数） ----------

def get_current_time(timezone: str = "JST") -> dict[str, Any]:
    tz = JST if timezone.upper() == "JST" else UTC
    now = datetime.now(tz)
    return {
        "timezone": timezone.upper(),
        "iso8601": now.isoformat(),
        "readable": now.strftime("%Y年%m月%d日 %H時%M分"),
        "weekday": "月火水木金土日"[now.weekday()] + "曜日",
    }


# ---------- `tool` の一覧 ----------
# description はモデルが「どの tool をいつ使うか」を判断する唯一の手がかり（第6回 02 の 1-4）。
# プロンプトの一部だと思って書く。

TOOLS: list[Tool] = [
    Tool(
        name="get_current_time",
        description=(
            "現在の日付と時刻を返す。"
            "「いま何時」「今日は何日」など、現在時刻を知らないと答えられない質問のときに使う。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "タイムゾーン。JST か UTC。既定は JST。",
                    "enum": ["JST", "UTC"],
                }
            },
            "required": [],
        },
        run=lambda **kw: get_current_time(kw.get("timezone", "JST")),
    ),
]

_BY_NAME = {t.name: t for t in TOOLS}


def all_tool_specs() -> list[dict[str, Any]]:
    """モデルに渡す`tool` の一覧。agent.py が毎ターンこの形で送る。"""
    return [t.spec() for t in TOOLS]


def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """モデルに指名された tool を実際に動かす。

    **ここで例外を外に投げない。**tool が1つ失敗しただけで会話全体が落ちるため（4-1 で見たもの）。
    失敗したという事実を結果として返せば、モデルはそれを読んで謝るか、別の言い方を試せる。
    """
    logger.info("tool requested by model",
                extra={"extra_fields": {"tool": name, "input": args}})
    tool = _BY_NAME.get(name)
    if tool is None:
        return {"error": f"{name} という tool はありません"}
    try:
        return tool.run(**args)
    except Exception as e:
        logger.exception("tool execution failed", extra={"extra_fields": {"tool": name}})
        return {"error": f"tool が使えませんでした: {e}"}
