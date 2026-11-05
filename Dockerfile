# 第4回で使う。このアプリを AWS Lambda のコンテナイメージとして動かすための定義。
#
# ふつうの FastAPI アプリ（uvicorn で 8080 番を待つ）を、そのまま Lambda に載せるための
# 仕掛けが Lambda Web Adapter。Lambda が受け取ったイベントを HTTP リクエストに変換して
# 8080 番へ流し、返ってきた HTTP レスポンスを Lambda の戻り値に変換してくれる。
# つまり「アプリ側は Lambda を一切意識しない」で済む。ローカルの uvicorn と同じコードが動く。
#
# CPU の種類は全員 x86_64（amd64）に揃える。template.yaml の Architectures: [x86_64] と対。
# Apple Silicon の Mac ではエミュレーションになるが、実測 17 秒で問題ない。
FROM --platform=linux/amd64 python:3.13-slim

# ↓ この1行が Lambda Web Adapter。/opt/extensions に置くと Lambda が拡張として起動する
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0-x86_64 /lambda-adapter /opt/extensions/lambda-adapter

# Python の出力をバッファせずそのまま標準出力へ流す（ログが即座に CloudWatch に出る）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# アダプタがアプリの起動完了を判断するために叩く先。ここが 200 を返すまでリクエストを流さない
ENV AWS_LWA_READINESS_CHECK_PATH=/healthz \
    AWS_LWA_PORT=8080

WORKDIR /app

# 依存だけ先に入れる。コードを変えてもここのキャッシュが効くのでビルドが速い
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# root 以外のユーザーで動かす
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
