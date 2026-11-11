"""アプリの設定をまとめて読む場所（第7回版。app/config.py を丸ごと差し替える）。

設定値はすべて環境変数から読む。コードに直接書かない。
ローカルでは .env ファイル、AWS では Lambda の環境変数（template.yaml で定義）から渡ってくる。
.env が無ければ、ここに書いた既定値で動く。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # このアプリの持ち主。AWS リソースの命名とログの絞り込みに使う
    student_id: str = "unset"

    # 動かしている場所。"local" か "aws"
    app_env: str = "local"

    # 画面の上に出す名前。自分のエージェントの名前に変えてよい
    app_name: str = "AI実践研修 エージェント"

    # ログの細かさ。INFO / DEBUG / WARNING
    log_level: str = "INFO"

    # --- 第4回で増えたもの ---

    # AWS のリージョン。Secrets Manager・Bedrock・DynamoDB を呼ぶときに使う
    aws_region: str = "ap-northeast-1"

    # 鍵そのもの。**手元の .env にだけ書く。**コードにも Git にも入れない
    demo_api_key: str = ""

    # 鍵の名前（Secrets Manager 上の名前）。AWS ではこちらだけ template.yaml から渡す
    demo_api_key_secret_name: str = ""

    # --- 第5回で増えたもの ---

    # 使う LLM。安いものに固定する。ここを高いモデルに変えると単価が17倍になる
    bedrock_model_id: str = "amazon.nova-lite-v1:0"

    # 1回の応答で生成させる最大トークン数。長文暴走の歯止め。公開 URL の裏にあるので必ず上限を持つ
    max_tokens: int = 1024

    # 応答のばらつき。0 に近いほど毎回同じ答えになる
    temperature: float = 0.3

    # --- 第6回で増えたもの ---

    # 会話履歴の置き場（DynamoDB のテーブル名）。**空なら履歴を使わない**（第5回と同じ1問1答）。
    # 手元は .env に、AWS は template.yaml から渡す。同じ名前を書けば手元と AWS が同じ履歴を読む
    conversation_table: str = ""

    # モデルに送る過去の発言の上限（件数）。1往復 ＝ user と assistant の2件なので、20 なら10往復ぶん。
    # 多いほど文脈は続くが、毎回の inputTokens が増える（＝ 料金が増える）
    max_history_messages: int = 20

    # 何日で自動的に消すか（DynamoDB の TTL）
    history_ttl_days: int = 7

    # --- 第7回で増えたもの ---

    # 1回の発話で、モデルに聞いてよい回数の上限。tool を1回使うと1ターン増える。
    # **止める条件が無いと、モデルが tool を呼び続けて課金だけが増える。**
    # 手元では .env で変えられる。AWS は既定値の 5 で動く
    max_agent_turns: int = 5


    # ---- ログイン（第4回で有効になる）------------------------------------
    # 手元（uvicorn）では False のまま。ログインせずに画面を触れる。
    # AWS にデプロイすると template.yaml が True を渡すので、ログインが要るようになる
    require_auth: bool = False

    # Cognito の2つ。**手では入れない。**template.yaml が Lambda の環境変数で渡す
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""


settings = Settings()
