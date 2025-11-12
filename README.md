# 社内向け給与明細自動取得・集計ツール (V6.1)
### 概要
給与明細Webサイト（palma-svc）に自動ログインし、全期間の明細データを取得、集計して output/年間サマリー_全期間.csv に保存する社内向けツールです。
V6.0にて処理ロジックをモジュール（main_controller, network_handler等）に分割し、V6.1でbatファイルからの実行に対応しました。
UIの表示には Streamlit を使用しています。
### 主な機能
給与明細サイトへの自動ログイン（ID/PWは初回成功時に core/.env に自動保存）
指定年または全期間（2019年～）の明細データ（支給額、時間外、有給情報など）の自動取得
取得した全データを output/年間サマリー_全期間.csv に蓄積保存
指定した年の「暦年サマリー（1-12月）」および「年度時間外（4-翌3月）」の集計・表示
#### 必須環境
Python 3.12 推奨
（注意： manual.html 記載の通り、Python 3.14以降では動作しないことが確認されています）
Pythonインストール時に**「Add Python to PATH」**（または「Add python.exe to PATH」）にチェックを入れる必要があります。
#### セットアップ (初回のみ)
- core フォルダに移動します。
- core/setup.bat をダブルクリックして実行します。
- requirements.txt に基づき、必要なライブラリ（streamlit, requests, beautifulsoup4等）がインストールされます。
#### 実行方法
- プロジェクトのルートフォルダ（core フォルダの外）にある apprun.bat をダブルクリックします。
- 自動的にコンソールが起動し、Streamlitサーバーが立ち上がりブラウザが開きます。
- ブラウザの画面でID/PWを入力し、「実行」または「全期間スキャン」ボタンを押してください。
#### フォルダ構成
```
project_root/
├── apprun.bat          (▲ 実行ファイル)
├── manual.html         (利用者向け手順書)
├── README.md           (このファイル)
│
├── output/             (※自動生成)
│   ├── 年間サマリー_全期間.csv
│   ├── app_log.log
│   └── debug_requests_network_log.txt
│
└── core/               (★ アプリ本体)
    ├── setup.bat         (▲ 初回セットアップ用)
    ├── app.py            (Streamlit UI本体)
    ├── main_controller.py (メイン処理フロー)
    ├── network_handler.py (通信・パース処理)
    ├── csv_handler.py    (CSV読込・保存)
    ├── summary_calculator.py (集計処理)
    ├── date_utils.py     (対象月生成)
    ├── requirements.txt  (依存ライブラリ)
    └── .env              (※ID/PW自動保存先)
```
