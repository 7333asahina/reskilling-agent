"""ログインしている人かどうかを確かめる場所。

なぜ自前で書くのか。
API Gateway なら「Cognitoオーソライザー」を選ぶだけで検証してくれる。
**Lambdaの関数URLにはその仕組みが無い。**（関数URLの認証方式は AWS_IAM か NONE の2つだけ）
だから NONE にしたうえで、届いたトークンをこの中で自分で検証する。

検証していないトークンは、ただの文字列。
「Authorizationヘッダが付いていた」ことは何の証明にもならない。誰でも付けられる。

確かめることは5つ。ひとつでも欠けると通ってしまう。

  1. 署名  — Cognitoの秘密鍵で署名されているか（偽造でないか）
  2. iss   — 自分のユーザープールが発行したものか（他人のプールのトークンを弾く）
  3. aud   — 自分のアプリ向けに発行されたものか
  4. token_use — IDトークンか（アクセストークンを代わりに出されても通さない）
  5. exp   — 期限が切れていないか
"""

import logging
from typing import Any

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


class _Verifier:
    """公開鍵(JWKS)を取ってきて、トークンを検証する。

    公開鍵はCognitoが公開しているURLから取る。毎回取りに行くと遅いので、
    PyJWKClient が中でキャッシュしてくれる。Lambdaが温まっている間は使い回される。
    """

    def __init__(self) -> None:
        self._client: PyJWKClient | None = None

    @property
    def issuer(self) -> str:
        return (
            f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}"
        )

    def _jwk_client(self) -> PyJWKClient:
        if self._client is None:
            # lifespan は鍵をキャッシュしておく秒数
            self._client = PyJWKClient(f"{self.issuer}/.well-known/jwks.json", lifespan=3600)
        return self._client

    def verify(self, token: str) -> dict[str, Any]:
        signing_key = self._jwk_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],          # Cognitoの署名方式。ここを緩めてはいけない
            audience=settings.cognito_client_id,   # 3. aud
            issuer=self.issuer,                    # 2. iss
            options={"require": ["exp", "iss", "aud", "token_use"]},
        )
        # 4. IDトークンであること。
        #    アクセストークンにも同じ署名が付いているので、種別を見ないと通ってしまう
        if claims.get("token_use") != "id":
            raise jwt.InvalidTokenError("IDトークンではありません")
        return claims


_verifier = _Verifier()


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPIの依存として使う。ログインしていなければ401を返してここで止める。

    Bedrockを呼ぶ前に弾くことが大事。認証を通す前にモデルを呼んだら、
    誰でも課金させられる。
    """
    # 開発中や、認証を入れる前の段階では素通しできるようにしておく
    if not settings.require_auth:
        return {"sub": "anonymous", "email": "(認証なし)"}

    if not settings.cognito_user_pool_id or not settings.cognito_client_id:
        # 設定が入っていないのに require_auth が真 ＝ 事故。素通しせず落とす
        logger.error("auth is required but cognito settings are missing")
        raise HTTPException(status_code=500, detail="認証の設定が入っていません")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="ログインしてください")

    token = authorization.split(" ", 1)[1].strip()

    try:
        claims = _verifier.verify(token)
    except jwt.ExpiredSignatureError:
        # 期限切れは「もう一度ログインし直せば済む」ので、画面側が区別できるようにする
        raise HTTPException(status_code=401, detail="ログインの有効期限が切れました") from None
    except jwt.PyJWTError as e:
        logger.warning("token rejected", extra={"extra_fields": {"reason": type(e).__name__}})
        raise HTTPException(status_code=401, detail="トークンが不正です") from None
    except Exception as e:  # 鍵の取得に失敗したときなど
        logger.exception("token verification failed")
        raise HTTPException(status_code=503, detail="認証の確認に失敗しました") from e

    return claims
