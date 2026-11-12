#!/usr/bin/env python3
"""MCP サーバーに JSON-RPC を1件送る（第8回 午前。リポジトリ直下に置く）。

    py rpc.py rpc-initialize.json          Mac は python3 rpc.py rpc-initialize.json

繋ぎ先は .env の MCP_URLS の1本目です。

## なぜ curl ではなく py なのか

繋ぎ先の関数 URL は **AWS_IAM 認証**です。リクエストに AWS の署名が付いていないと 403 で
断られます。curl は署名を作れないので、ここでは Python から送ります。
署名を付けているのは下の3行です。

    req = AWSRequest(method="POST", url=url, data=body, headers=headers)
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    SigV4Auth(creds, "lambda", region).add_auth(req)

使っているのは、第4回で `aws configure` に設定した自分のアクセスキーです。
**署名が何をしているかは第9回**で扱います。第8回は、署名が要ることと、
それが `aws configure` の設定から作られることだけ分かれば先に進めます。
"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from app.config import settings

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)

    base = settings.mcp_urls.split(",")[0].strip().rstrip("/")
    if not base:
        print("MCP_URLS が空です。.env に接続先を書いてください")
        return 2

    url = base + "/mcp"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    # 127.0.0.1 は AWS のサービスではないので署名しない（第9回で繋ぐ相手がこれ）
    from urllib.parse import urlparse
    if urlparse(url).hostname not in LOCAL_HOSTS:
        creds = boto3.Session().get_credentials()
        if creds is None:
            print("AWS の資格情報が見つかりません。aws configure を実行してください")
            return 2
        req = AWSRequest(method="POST", url=url, data=body, headers=dict(headers))
        SigV4Auth(creds.get_frozen_credentials(), "lambda", settings.aws_region).add_auth(req)
        headers = dict(req.headers)

    print(f"POST {url}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("-" * 60)

    try:
        with urlopen(Request(url, data=body, headers=headers, method="POST"), timeout=60) as res:
            answer = json.load(res)
    except HTTPError as e:
        print(f"HTTP {e.code}")
        print(e.read().decode("utf-8", "replace")[:500])
        return 1
    except URLError as e:
        print(f"繋がりませんでした: {e.reason}")
        return 1

    print(json.dumps(answer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
