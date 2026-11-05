# reskilling — AI 実践研修 本番リポジトリ（雛形）

15日間で育てる、自分のエージェントの入れ物です。第3回に `reskilling-answers` の `main` から自分のリポジトリを作ります。

## 動かす（第3回）

Windows
```
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements-dev.txt
py -m uvicorn app.main:app --reload --port 8080
```

Mac
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 -m uvicorn app.main:app --reload --port 8080
```

ブラウザで http://127.0.0.1:8080 を開く。API の一覧は http://127.0.0.1:8080/docs 。

## 中身

```
app/main.py          エンドポイント。/healthz  /  /api/chat（いまは受け取った文字を返すだけ）
app/web/index.html   画面。見た目は自由に変えてよい。id の付いた要素と /api/chat の呼び方は変えない
app/config.py        設定。全部環境変数から読む。手元は .env、AWS は template.yaml（第4回）
app/logging_conf.py  ログ。1行1件の JSON（第4回で CloudWatch に出る）
tests/               器のテスト。pytest で動く。ネットワークには出ない
pytest.ini           テストは tests/ だけを見る（直下に置いたスクリプトを拾わない）
requirements.txt     アプリが動くのに要るもの。**AWS のコンテナにはこれだけ入る**
requirements-dev.txt 上に pytest と httpx を足したもの。手元で開発するとき用
Dockerfile           第4回で AWS Lambda に載せるときの定義（x86_64）
```

## 回ごとのブランチ

**このリポジトリは、回ごとにブランチが分かれています。**
自分のリポジトリで手が止まったとき、ここを見れば「正解の形」が確かめられます。

```
cd ~/answers
git checkout lesson-08        # 第8回の終わりの状態
```

| ブランチ | 何の状態か |
|---|---|
| `main` | 第3回の朝。ここから自分のリポジトリを作ります |
| `lesson-03` | 第3回の終わり |
| `lesson-04` | 第4回の終わり |
| `lesson-05` | 第5回の終わり |
| `lesson-06` | 第6回の終わり |
| `lesson-07` | 第7回の終わり |
| `lesson-08` | 第8回の終わり |
| `lesson-09` | 第9回の終わり |
| `lesson-10` | 第10回の終わり |
| `lesson-12` | 第12回の終わり |
| `lesson-13` | 第13回の終わり |
| `lesson-14` | 第14回の終わり |

**`lesson-07` だけ、少し違います。**`app/tools.py` と `tests/test_health.py` は `02` 3-3 の時点で、
`run_tool()` に `try` はまだ入っていません。`02` 4-1 で「`tool` が1つ失敗すると会話が落ちる」を
自分の画面で見てから、4-2 でリポジトリ直下の `run_tool.py` と `test_tool_failure.py` を貼ります。

**`lesson-11` と `lesson-15` のブランチはありません。**新しく配るファイルが無いためです。

**ここから丸ごとコピーしないでください。**手順書が指定したファイルと関数だけをコピーします。
どこを貼るかは、各回の手順書の「コピー元／どこを／コピー先」の表にあります。

## 回ごとに何が増えるか

| 回 | 増えるもの |
|---|---|
| 第3回 | 自分の画面。`/api/suggestions` |
| 第4回 | `.env`・`app/secrets.py`・`template.yaml`・`samconfig.toml`。Docker → ECR → Lambda（公開 URL）・CloudWatch Logs |
| 第5回〜 | `/api/chat` の中身が LLM（Amazon Bedrock）に。ツール・履歴・MCP・RAG |
| 第7回 | `app/tools.py`・`app/agent.py`・`tool_loop.py`・`run_tool.py`・`test_tool_failure.py`。`app/llm.py` は消える。**AWS のリソースは増えない** |
| 第8回 | `app/mcp_client.py`・`rpc.py`・`show_tools.py`・`check_cache.py`・`count_tools.py`。ファイブ社の Gmail・カレンダー MCP につなぐ。**AWS のリソースは増えない。デプロイもしない** |
| 第9回 | `directory_mcp/`・`start.sh`。コンテナが `uvicorn` を2本起こす（`8081` は `127.0.0.1`）。**AWS のリソースは増えない** |
| 第10回 | `trace_tools.py`・`rpc-tools-call-mail.json` ほか。ファイブ社の MCP のメールの `tool` につなぐ。**AWS のリソースは増えない。デプロイもしない** |
| 第12回 | `app/knowledge.py`（`app/tools.py` に `search_documents` が増える）・`turns.py`・`cut_history.py`・`retrieve.py`・`embed.py`・`chunk.py`・`rag-docs/`。ファイブ社の社内文書の検索につなぐ。**検索先はファイブ社のもの。AWS のリソースは増えない** |
| 第13回 | `template.yaml` に `KnowledgeBaseId` と `bedrock:Retrieve`。**デプロイする回**（第5回・第9回と同じ形）。`app/` は変わらない |
| 第14回 | `eval.py`・`eval_cases.json`。`app/` は変わらない。**AWS のリソースは増えない** |
