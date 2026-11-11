"""システムプロンプト（第7回版。app/prompt.py を丸ごと差し替える）。

system は「利用者の発言の前に、アプリが毎回付ける指示」。役割・答え方・今日の日付をここに書く。
**モデルの中に時計もカレンダーも無い。**日付を渡さないと「今日は何日」に答えられない（第5回で見た）。

第6回版との違いは「ツールの使い方」の3行。第6回 02 の 1-5 で CLI を使って確かめたことを、
そのままアプリの system に入れてある。**「使う場面」だけを書くと、関係ない質問でも tool を呼ぶ**
（実測で3回中3回。RAG とは何かを聞いて現在時刻の tool を呼んだ）。「使わない場面」を1行足すと収まる。

文面を変えるのはこのファイルだけ。agent.py も main.py も触らない。
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), "JST")
WEEKDAYS = "月火水木金土日"

# {now} と {week} は build_system_prompt() が毎回埋める
SYSTEM_PROMPT_TEMPLATE = """あなたは社内業務を手伝う日本語のアシスタントです。

いまの日時（日本時間）: {now}
今週: {week}

答え方
- 簡潔に、事実だけを述べる
- 分からないことは分からないと言う。推測で埋めない
- 会話の前の発言に書かれていることは、そこから答える
- 最終的な答えだけを書く。考えた過程やタグ（<thinking> など）は出力しない

ツールの使い方
- 現在時刻など、**自分では知りようのないこと**は必ずツールを使って調べる
- 一般的な知識・用語の説明・文章の作成・雑談は、ツールを使わず自分の知識で答える
- **同じツールを同じ引数で2回呼ばない。**1度呼んだツールの結果で答えをまとめる
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
