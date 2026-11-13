"""社員名簿のデータ。**コードに直書きする。**

データベースを使わない理由は3つ。

  1. 第4章に使える時間は第9回AMの3時間だけ。DBを足すと入らない
  2. MCPは「tool の渡し方の規格」であって、データの持ち方とは無関係。
     ここでDBを持ち出すと、覚えることが2つになって焦点がぼやける
  3. 名簿は**答えが1行に定まるデータ**（D-25の軸②）。
     この性質さえ見えれば、置き場所がリストでもDBでも話は変わらない

実務で30名を超えるならDynamoDBやRDSに移すが、そのときも
このファイルの外（main.py）は1行も変わらない。差し替えられるのが tool の形の良さ。

**同姓の社員をわざと2名入れてある**（田中健一・田中美咲）。
「田中さん」で引くと2件返る。文字一致の検索は、こういうときに
勝手に1件へ絞り込まない。そこが意味検索（ベクトル）との違いになる（D-25）。
"""

from typing import Any

PEOPLE: list[dict[str, Any]] = [
    # --- 役員室 -------------------------------------------------------------
    {"id": "E001", "name": "佐藤健一郎", "kana": "さとうけんいちろう",
     "dept": "役員室", "title": "代表取締役社長", "ext": "2001", "email": "k.sato@example.co.jp"},
    {"id": "E002", "name": "高橋隆明", "kana": "たかはしたかあき",
     "dept": "役員室", "title": "専務取締役", "ext": "2002", "email": "t.takahashi@example.co.jp"},
    {"id": "E003", "name": "中村由美子", "kana": "なかむらゆみこ",
     "dept": "役員室", "title": "常務取締役", "ext": "2003", "email": "y.nakamura@example.co.jp"},
    {"id": "E004", "name": "渡辺里奈", "kana": "わたなべりな",
     "dept": "役員室", "title": "秘書", "ext": "2005", "email": "r.watanabe@example.co.jp"},

    # --- 経営企画部 ---------------------------------------------------------
    {"id": "E005", "name": "伊藤大輔", "kana": "いとうだいすけ",
     "dept": "経営企画部", "title": "部長", "ext": "2110", "email": "d.ito@example.co.jp"},
    {"id": "E006", "name": "山本恵", "kana": "やまもとめぐみ",
     "dept": "経営企画部", "title": "課長", "ext": "2111", "email": "m.yamamoto@example.co.jp"},
    {"id": "E007", "name": "松本亮", "kana": "まつもとりょう",
     "dept": "経営企画部", "title": "主任", "ext": "2112", "email": "r.matsumoto@example.co.jp"},

    # --- 営業部 -------------------------------------------------------------
    {"id": "E008", "name": "田中健一", "kana": "たなかけんいち",
     "dept": "営業部", "title": "部長", "ext": "2210", "email": "k.tanaka@example.co.jp"},
    {"id": "E009", "name": "井上拓也", "kana": "いのうえたくや",
     "dept": "営業部 第1課", "title": "課長", "ext": "2211", "email": "t.inoue@example.co.jp"},
    {"id": "E010", "name": "木村沙織", "kana": "きむらさおり",
     "dept": "営業部 第1課", "title": "一般", "ext": "2212", "email": "s.kimura@example.co.jp"},
    {"id": "E011", "name": "清水健太", "kana": "しみずけんた",
     "dept": "営業部 第2課", "title": "課長", "ext": "2213", "email": "k.shimizu@example.co.jp"},
    {"id": "E012", "name": "森田千夏", "kana": "もりたちなつ",
     "dept": "営業部 第2課", "title": "一般", "ext": "2214", "email": "c.morita@example.co.jp"},
    {"id": "E013", "name": "田中美咲", "kana": "たなかみさき",
     "dept": "営業部 第2課", "title": "主任", "ext": "2215", "email": "m.tanaka@example.co.jp"},

    # --- 総務部 -------------------------------------------------------------
    {"id": "E014", "name": "加藤正樹", "kana": "かとうまさき",
     "dept": "総務部", "title": "部長", "ext": "2310", "email": "m.kato@example.co.jp"},
    {"id": "E015", "name": "吉田香織", "kana": "よしだかおり",
     "dept": "総務部", "title": "課長", "ext": "2311", "email": "k.yoshida@example.co.jp"},
    {"id": "E016", "name": "山田翔", "kana": "やまだしょう",
     "dept": "総務部", "title": "一般", "ext": "2312", "email": "s.yamada@example.co.jp"},

    # --- 人事部 -------------------------------------------------------------
    {"id": "E017", "name": "佐々木涼子", "kana": "ささきりょうこ",
     "dept": "人事部", "title": "部長", "ext": "2410", "email": "r.sasaki@example.co.jp"},
    {"id": "E018", "name": "岡田秀人", "kana": "おかだひでと",
     "dept": "人事部", "title": "課長", "ext": "2411", "email": "h.okada@example.co.jp"},

    # --- 経理部 -------------------------------------------------------------
    {"id": "E019", "name": "藤井康彦", "kana": "ふじいやすひこ",
     "dept": "経理部", "title": "部長", "ext": "2510", "email": "y.fujii@example.co.jp"},
    {"id": "E020", "name": "中川真理", "kana": "なかがわまり",
     "dept": "経理部", "title": "課長", "ext": "2511", "email": "m.nakagawa@example.co.jp"},
    {"id": "E021", "name": "大西直樹", "kana": "おおにしなおき",
     "dept": "経理部", "title": "一般", "ext": "2512", "email": "n.onishi@example.co.jp"},

    # --- 法務部 -------------------------------------------------------------
    {"id": "E022", "name": "石川智子", "kana": "いしかわともこ",
     "dept": "法務部", "title": "部長", "ext": "2610", "email": "t.ishikawa@example.co.jp"},
    {"id": "E023", "name": "長谷川学", "kana": "はせがわまなぶ",
     "dept": "法務部", "title": "課長", "ext": "2611", "email": "m.hasegawa@example.co.jp"},

    # --- 情報システム部 -----------------------------------------------------
    {"id": "E024", "name": "村上涼太", "kana": "むらかみりょうた",
     "dept": "情報システム部", "title": "部長", "ext": "2710", "email": "r.murakami@example.co.jp"},
    {"id": "E025", "name": "前田由紀", "kana": "まえだゆき",
     "dept": "情報システム部", "title": "課長", "ext": "2711", "email": "y.maeda@example.co.jp"},
    {"id": "E026", "name": "三浦悠", "kana": "みうらゆう",
     "dept": "情報システム部", "title": "一般", "ext": "2712", "email": "y.miura@example.co.jp"},

    # --- 購買部 -------------------------------------------------------------
    {"id": "E027", "name": "横山剛", "kana": "よこやまつよし",
     "dept": "購買部", "title": "課長", "ext": "2810", "email": "t.yokoyama@example.co.jp"},

    # --- 広報部 -------------------------------------------------------------
    {"id": "E028", "name": "内田明日香", "kana": "うちだあすか",
     "dept": "広報部", "title": "課長", "ext": "2910", "email": "a.uchida@example.co.jp"},

    # --- 商品開発部 ---------------------------------------------------------
    {"id": "E029", "name": "福田直人", "kana": "ふくだなおと",
     "dept": "商品開発部", "title": "部長", "ext": "3010", "email": "n.fukuda@example.co.jp"},
    {"id": "E030", "name": "岩崎佳奈", "kana": "いわさきかな",
     "dept": "商品開発部", "title": "一般", "ext": "3011", "email": "k.iwasaki@example.co.jp"},
]

BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in PEOPLE}
