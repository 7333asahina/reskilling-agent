"""アプリの設定をまとめて読む場所。

設定値はすべて環境変数から読む。コードに直接書かない。
ローカルでは .env ファイル、AWS では Lambda の環境変数から渡ってくる（第4回）。
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

    # 使うリージョン。東京に固定する（第1回 04 の 1-3）
    aws_region: str = "ap-northeast-1"

    # ---- ログイン（第4回で有効になる）------------------------------------
    # 手元（uvicorn）では False のまま。ログインせずに画面を触れる。
    # AWS にデプロイすると template.yaml が True を渡すので、ログインが要るようになる
    require_auth: bool = False

    # Cognito の2つ。**手では入れない。**template.yaml が Lambda の環境変数で渡す
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""


settings = Settings()
