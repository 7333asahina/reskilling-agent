#!/bin/sh
# コンテナの中で uvicorn を2本起動する（第9回。リポジトリ直下の start.sh）。
#
#   :8080  エージェント本体。Lambda Web Adapter が外からのリクエストを流す先
#   :8081  社内名簿の MCP サーバー。**127.0.0.1 にだけ縛る**
#
# 8081 は外に出ない。LWA が繋ぐのは AWS_LWA_PORT（=8080）だけなので、
# 公開 URL からも 8081 には届かない。エージェント本体だけが http://127.0.0.1:8081/mcp を叩ける。
#
# **パスで生やさずポートを分ける理由がここ。**同じ 8080 に /mcp として生やすと、
# 公開 URL に認証が無い状態では、名簿が誰からでも引ける。
set -e

# MCP サーバーを裏で起動する。落ちても本体は動き続ける
# （エージェント側は MCP に繋がらなければ、その tool だけ諦めて会話を続ける）
uvicorn directory_mcp.main:app --host 127.0.0.1 --port "${DIRECTORY_MCP_PORT:-8081}" --log-level warning &

# 本体は exec で置き換える。PID 1 のままにしておくと、停止の合図がそのまま uvicorn に届く
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
