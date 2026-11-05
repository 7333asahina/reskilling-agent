/api/chat が受け取るもの: 利用者からの入力とどの会話の続きかを示す（例: message と session_id）
/api/chat が返すもの:     受け取った文字をそのまま返す、対応時間（例: reply と実測値）
第5回で差し替える場所:   例: chat 関数で第5回で、この中身を Bedrock の呼び出しに差し替える。
req.message（例: chat 関数の中の reply = ... の行
