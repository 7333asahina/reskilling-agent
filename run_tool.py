# app/tools.py の run_tool 関数を、これに差し替える（第7回 02 の 4-2）。
# 増えるのは try と except の4行だけ。

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
