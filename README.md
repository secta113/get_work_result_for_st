# 給与明細自動取得・集計ツール (V6.3)

これは、特定の給与明細Webサイト（palma-svc）からデータを自動取得し、ローカルにCSVとして保存・集計するためのPythonスクリプトです。
UIの表示・操作には Streamlit を使用しています。

### 📖 概要
V6.2にてID/PWの暗号化に対応しました。
**V6.3では、暗号化キーにPC固有のMACアドレスを使用する方式に変更し、キー設定の手間を不要にしました。**

### ✨ 主な機能
* 給与明細サイトへの自動ログイン
* ID/PWは初回成功時に `core/.env` に**自動で暗号化して保存**されます。
* ログインURLのパラメータ (`c=...`) も `core/.env` で管理されます。
* 指定年または全期間（2019年～）の明細データ（支給額、時間外、有給情報など）の自動取得
* 取得した全データを `output/年間サマリー_全期間.csv` に蓄積保存
* 指定した年の「暦年サマリー（1-12月）」および「年度時間外（4-翌3月）」の集計・表示

---

### 🐍 必要なもの (Prerequisites)
* **Python 3.12** 推奨
    * *（注意： Python 3.14以降ではStreamlitの依存関係の問題で動作しないことが確認されています）*
* Pythonインストール時に**「Add Python to PATH」**（または「Add python.exe to PATH」）にチェックを入れる必要があります。

---

### 🚀 インストール & セットアップ

1.  **リポジトリのクローン**
    ```bash
    git clone https://github.com/secta113/get_work_result_for_st.git
    cd get_work_result_for_st
    ```

2.  **依存ライブラリのインストール**
    `core` フォルダに移動し、`setup.bat` を実行するか、ターミナルで直接 `pip` コマンドを実行します。
    ```bash
    cd core
    pip install -r requirements.txt
    ```
    *(主なライブラリ: `streamlit`, `requests`, `beautifulsoup4`, `cryptography`, `python-dotenv`)*

3.  **`.env` ファイルのセットアップ**
    `core` フォルダに `.env` ファイルを**新規作成**し、以下の内容を記述します。
    ```ini
    MY_LOGIN_ID=""
    MY_PASSWORD=""
    LOGIN_COMPANY_CODE="your_campany_code"
    ```
    *(`LOGIN_COMPANY_CODE` はログインページの `?c=` パラメータです)*

---

### 🏃 実行方法
下記のどちらかをご利用ください。

1.  **batファイルで実行 (Windows)**
    * プロジェクトのルートフォルダ（`core` の親）にある `apprun.bat` をダブルクリックします。

2.  **コマンドで実行 (Mac / Linux / Windows)**
    * ターミナルで `core` フォルダに移動し、`streamlit` コマンドを実行します。
    ```bash
    cd core
    streamlit run app.py
    ```

自動的にブラウザが起動します。画面でID/PWを入力し、「実行」ボタンを押してください。

---

### ⚠️ 仕様・注意点

* **PC固有の暗号化 (マシンロック)**
    * 本ツールは、ID/PWを暗号化する際、PC固有のMACアドレスをキーとして使用します。
    * これにより、`core` フォルダ一式（`.env` を含む）を**別のPCにコピーしても、暗号化されたID/PWを復号できず、動作しません**。
    * PCを移行（買い替え）する際は、新しいPCで再度 `setup.bat` を実行し、初回からログインし直す必要があります（古い `.env` は引き継げません）。
* **ランダムMACアドレスに関する注意**
    * Windows 10/11 や一部のノートPCでは、Wi-Fi接続時に「ランダムなハードウェアアドレス」機能が有効になっている場合があります。
    * この機能が有効だと、PCを再起動するたびにMACアドレスが変わり、`.env` が復号できなくなる可能性があります。
    * もしログインが頻繁に失敗する（`.env` が読めなくなる）場合は、OSのWi-Fi設定で「ランダムなハードウェアアドレス」をオフにしてから、再度ログインし直してください。

---

### 📁 フォルダ構成
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
    ├── encryption_utils.py (暗号化ライブラリ)
    └── .env              ※ID/PW(暗号化), CompanyCode 保存先)
```
---

### ⚠️ 免責事項 (Disclaimer)
* 本ツールは、個人の利用範囲におけるデータ集計の効率化を目的としています。
* ツールの使用にあたっては、対象Webサイト（palma-svc）の利用規約を遵守してください。
* 本ツールの使用によって生じたいかなる直接的または間接的な損害についても、開発者は一切の責任を負いません。自己責任でご利用ください。
