"""Bedrock の Converse API を Python から1回呼ぶ（第5回 01 の 2-1）。

    python3 call_llm.py    # Mac
    py call_llm.py         # Windows

アプリとは無関係に、これ1つで動く。午前に CLI で送ったものと同じ messages を、
boto3 で送っている。返ってくる形も同じ。
"""

import boto3

# AWS の認証情報は aws configure が保存したものを boto3 が自動で読む（第4回 04 の 2-3）
client = boto3.client("bedrock-runtime", region_name="ap-northeast-1")

response = client.converse(
    modelId="amazon.nova-lite-v1:0",
    messages=[
        {"role": "user", "content": [{"text": "日本で一番高い山は？1行で答えて"}]},
    ],
    inferenceConfig={"maxTokens": 200, "temperature": 0.3},
)

# 返ってきた辞書から、答えの文字と、使ったトークン数を取り出す
print(response["output"]["message"]["content"][0]["text"])
print(response["usage"])
print(response["stopReason"])
