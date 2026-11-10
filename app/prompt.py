"""システムプロンプト（第6回。app/prompt.py として新しく置く）。

system は「利用者の発言の前に、アプリが毎回付ける指示」。役割・答え方・今日の日付をここに書く。
**モデルの中に時計もカレンダーも無い。**日付を渡さないと「今日は何日」に答えられない（第5回で見た）。

文面を変えるのはこのファイルだけ。llm.py も main.py も触らない。
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), "JST")
WEEKDAYS = "月火水木金土日"

# {now} と {week} は build_system_prompt() が毎回埋める
SYSTEM_PROMPT_TEMPLATE = """あなたは株式会社ファイブの社内アシスタント「ファイブくん」で
す。

いまの日時（日本時間）: {now}
今週: {week}

答え方
- 簡潔に、事実だけを述べる
- 分からないことは分からないと言う。推測で埋めない
- 会話の前の発言に書かれていることは、そこから答える
- 最終的な答えだけを書く。考えた過程やタグ（<thinking> など）は出力しない
"""


def build_system_prompt(now: datetime | None = None) -> str:
    """毎回その場で組み立てる。**定数にしてはいけない。**

    Lambda は温まっている間コードを使い回すので、ファイルの読み込み時に日付を埋めてしまうと、
    最初のリクエストの日付が翌日以降も使われ続ける。

    今週の曜日と日付の対応表も入れる。**モデルに曜日を数えさせない**ため。
    表があれば「明後日」「金曜日」を引き算せずに日付に直せる。約 75 トークン。
    """
    n = now or datetime.now(JST)
    stamp = f"{n:%Y年%m月%d日}（{WEEKDAYS[n.weekday()]}）{n:%H:%M}"
    monday = n.date() - timedelta(days=n.weekday())
    week = " ".join(
        f"{WEEKDAYS[i]}{(monday + timedelta(days=i)).month}/{(monday + timedelta(days=i)).day}"
        for i in range(7)
    )
    return SYSTEM_PROMPT_TEMPLATE.format(now=stamp, week=week)
