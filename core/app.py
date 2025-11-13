# --- app.py ---
# Streamlit を使用したフロントエンドアプリケーション
# 役割:
# 1. ユーザーインターフェース (UI) の構築
# 2. ユーザー入力 (ID, PW, 対象年) の受付
# 3. main_controller への処理の委譲
# 4. 処理結果（サマリー）の表示
# 5. 必須モジュールのインポートとロギング、パスの初期設定

import datetime
import os
import sys
import logging
from dotenv import load_dotenv
import re 

# --- Streamlit ---
import streamlit as st 

# --- 暗号化モジュールのインポート ---
try:
    # 復号関数とライブラリ利用可否フラグをインポート
    from encryption_utils import decrypt, CRYPTOGRAPHY_AVAILABLE
except ImportError:
    st.error("エラー: 必須モジュール (encryption_utils.py) の読み込みに失敗しました。")
    st.stop()
except Exception as e_init_enc:
    st.error(f"エラー: 暗号化モジュールの初期化中に予期せぬエラーが発生しました。\n{e_init_enc}")
    st.stop()


# --- メインロジック (Controller) をインポート ---
try:
    from main_controller import run_main_logic
except ImportError as e:
    st.error(f"エラー: 必須モジュールの読み込みに失敗しました。\n{e}")
    st.error("date_utils.py, csv_handler.py, summary_calculator.py, network_handler.py, main_controller.py が app.py と同じ場所にあるか確認してください。")
    logging.critical(f"起動失敗: モジュールインポートエラー: {e}", exc_info=True)
    st.stop()
except Exception as e_init:
    st.error(f"エラー: 初期化中に予期せぬエラーが発生しました。\n{e_init}")
    logging.critical(f"起動失敗: {e_init}", exc_info=True)
    st.stop()


# --- パス設定 ---
# PyInstaller で EXE化された場合と、Pythonスクリプトとして実行された場合で
# 基準となるパス (APP_BUNDLE_DIR) とプロジェクトルート (ROOT_DIR) を動的に設定する

if getattr(sys, 'frozen', False):
    # (EXE実行時)
    # EXE実行時は、PyInstallerが展開する一時フォルダ (sys._MEIPASS) ではなく、
    # 実行時のカレントワーキングディレクトリ (apprun.bat で cd core される想定) を基準とする
    APP_BUNDLE_DIR = os.path.abspath(os.getcwd()) 
    
    # EXE (sys.executable) が置かれているディレクトリをプロジェクトルートとする
    ROOT_DIR = os.path.dirname(sys.executable) 
    
    # .bat から .py を実行するハイブリッドなケースを考慮
    if not sys.executable.endswith(".exe"):
        # CWD (core) の親ディレクトリ (project) を ROOT_DIR とする
        ROOT_DIR = os.path.abspath(os.path.join(os.path.abspath(os.getcwd()), "..")) 
else:
    # (Pythonスクリプト実行時 / .batからのPython実行時)
    # apprun.bat で cd core されることを想定し、CWD (core) を基準とする
    APP_BUNDLE_DIR = os.path.abspath(os.getcwd())
    # CWD (core) の親ディレクトリ (project) を ROOT_DIR とする
    ROOT_DIR = os.path.abspath(os.path.join(APP_BUNDLE_DIR, ".."))

# .env ファイルは app.py と同じディレクトリ (core) にあると想定
env_path = os.path.join(APP_BUNDLE_DIR, ".env")
load_dotenv(env_path) 

# --- logging のセットアップ ---
# ログファイルはプロジェクトルートの 'output' フォルダに保存する
output_dir = os.path.join(ROOT_DIR, "output")
os.makedirs(output_dir, exist_ok=True) 
log_file_path = os.path.join(output_dir, "app_log.log") 

# ロガーをグローバルに設定 (各モジュールで getLogger(__name__) により使用される)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s', # モジュール名(name) を含める
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler() # コンソールにも出力
    ]
)
logger = logging.getLogger(__name__) # app.py 専用ロガー

# デバッグ用に設定パスを出力
print(f"APP_BUNDLE_DIR (app.py/.envの場所): {APP_BUNDLE_DIR}")
print(f"ROOT_DIR (outputの場所): {ROOT_DIR}")
print(f".envファイルの読込パス: {env_path}")
logging.info(f"Log file path: {log_file_path}")
# --- パス設定ここまで ---


# ===============================================
# ▼▼▼ Streamlit の UI と メインロジック ▼▼▼
# ===============================================

# --- 1. UIの定義 ---
st.set_page_config(page_title="給与明細 自動取得", layout="centered")
st.title("給与明細 自動取得ツール 🤖 (V6.2)") # バージョン表示
st.write("（V6.2: .env へのID/PW暗号化保存 / CompanyCodeを .env に移行）")
logging.info("Streamlit UI ページがロードされました。")

# --- cryptography のインストールチェック ---
if not CRYPTOGRAPHY_AVAILABLE:
    st.error("""
    エラー: 暗号化ライブラリ (cryptography) が見つかりません。
    
    ID/パスワードの安全な保存のため、以下のコマンドを実行してライブラリをインストールしてください:
    
    `pip install cryptography`
    
    インストール後、アプリケーションを再起動してください。
    """)
    logging.critical("cryptography ライブラリが見つかりません。ID/PWが平文で保存されます。")


# --- .env からの読み込みと「復号」 ---
try:
    # .env から暗号化された可能性のある文字列を読み込む
    initial_id_encrypted = os.getenv("MY_LOGIN_ID", "")
    initial_pw_encrypted = os.getenv("MY_PASSWORD", "")
    
    # decrypt 関数は、平文や復号失敗時もそのまま文字列を返す設計
    initial_id = decrypt(initial_id_encrypted) if initial_id_encrypted else ""
    initial_pw = decrypt(initial_pw_encrypted) if initial_pw_encrypted else ""
    
    logging.info(".env から ID/PW を読み込み、復号処理を実行しました。")
except Exception as e_decrypt:
    st.error(f"エラー: .env ファイルの復号中にエラーが発生しました。\n{e_decrypt}")
    logging.error(f".env の復号に失敗: {e_decrypt}", exc_info=True)
    initial_id = "" # エラー時は安全のため空にする
    initial_pw = ""

current_year = datetime.date.today().year

# --- ユーザー入力フォーム ---
with st.form(key='my_form'):
    login_id = st.text_input("ログインID", value=initial_id)
    password = st.text_input("パスワード", value=initial_pw, type="password")
    
    target_year_ui = st.number_input(
        "対象年（西暦） [サマリー表示用]", 
        value=current_year, 
        min_value=2019, max_value=2100,
        help="[実行]時は取得対象、[全期間スキャン]時はサマリー表示対象として使われます。"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        submit_button = st.form_submit_button(label='実行 (指定年)', use_container_width=True)
    with col2:
        scan_all_button = st.form_submit_button(label='全期間スキャン (2019年～)', use_container_width=True, type="secondary")

# 処理中のステータスを表示するためのプレースホルダー
status_placeholder = st.empty()

# --- 2. 実行ボタンが押された後の処理 ---

if submit_button or scan_all_button:
    
    logging.info(f"ボタンが押されました。UI指定年: {target_year_ui}")
    
    if not login_id or not password:
        st.error("ログインIDとパスワードを入力してください。")
        logging.warning("IDまたはパスワードが未入力のため処理を中断しました。")
    else:
        status_placeholder.info("処理を開始します...")
        
        # どちらのボタンが押されたかでスキャンモードを決定
        run_mode_is_full_scan = scan_all_button 
        
        # --- メインコントローラ呼び出し ---
        try:
            with st.spinner('メイン処理を実行中... (CSV読込/ネットワーク/CSV保存/集計)'):
                success, result_data = run_main_logic(
                    login_id=login_id, 
                    password=password, 
                    ui_target_year=target_year_ui, 
                    run_mode_is_full_scan=run_mode_is_full_scan, 
                    root_dir=ROOT_DIR, # プロジェクトルートパス
                    env_path=env_path, # .env ファイルのパス
                    status_placeholder=status_placeholder # UIステータス更新用
                )
            
            # .env 保存失敗時などの警告を処理
            if success and result_data.get("warning"):
                st.warning(result_data.get("warning"))
            
        except Exception as e_main:
            success = False
            result_data = {"error": f"メイン処理の実行中に予期せぬエラーが発生しました:\n{e_main}"}
            logging.error(f"run_main_logic 呼び出し中にクラッシュ: {e_main}", exc_info=True)
            
        
        # --- 3. 実行結果の表示 ---
        
        if not success:
            # エラー表示
            error_message = result_data.get("error", "不明なエラーが発生しました。")
            status_placeholder.error(f"エラー:\n{error_message}")
            logging.error(f"処理が失敗しました: {error_message}")
            st.stop()

        # --- 正常終了 (サマリー表示) ---
        
        st.subheader(f"--- {result_data.get('ui_target_year', target_year_ui)}年 (UI指定年) サマリー ---")
        
        final_data_ui = result_data.get("final_data_ui", [])
        
        if final_data_ui:
            # Controller から渡された計算済みデータを使用
            summary_data_rekigun = result_data.get("summary_data_rekigun", {})
            summary_nendo_overtime = result_data.get("summary_nendo_overtime", 0.0)
            csv_path_ui_rel = result_data.get("csv_path", "output/不明")

            # --- サマリーメッセージ生成 ---
            summary_message = f"CSVファイル更新完了: **{csv_path_ui_rel}**\n\n"
            summary_message += f"### {target_year_ui}年 年間サマリー (合計 {len(final_data_ui)} 件)\n"
            summary_message += f"- **総支給額 (暦年 {target_year_ui}/1～12)**: {summary_data_rekigun.get('total_pay', 0):,.0f} 円\n"
            summary_message += f"- **差引支給額 (暦年 {target_year_ui}/1～12)**: {summary_data_rekigun.get('total_net_pay', 0):,.0f} 円\n"
            summary_message += f"- **総時間外 (暦年 {target_year_ui}/1～12)**: {summary_data_rekigun.get('total_overtime', 0.0):,.2f} 時間\n"
            summary_message += f"- **年度時間外 ({target_year_ui}/4～{target_year_ui+1}/3)**: **{summary_nendo_overtime:,.2f} 時間**\n"
            
            # 最新月の有給情報を表示 (N/A を考慮)
            def format_latest_value(value, unit):
                if isinstance(value, (int, float)):
                    if unit == "日":
                        return f"{value:,.1f} {unit}" # 0.5日
                    else:
                        return f"{value:,.2f} {unit}" # 0.50時間
                return f"{value}" # "N/A"

            summary_message += f"- **有給消化時間 (最新月)**: {format_latest_value(summary_data_rekigun.get('latest_paid_leave_time', 'N/A'), '時間')}\n" 
            summary_message += f"- **有給使用日数 (最新月)**: {format_latest_value(summary_data_rekigun.get('latest_paid_leave_used_days', 'N/A'), '日')}\n"
            summary_message += f"- **有給残日数 (最新月)**: {format_latest_value(summary_data_rekigun.get('latest_paid_leave_remaining_days', 'N/A'), '日')}\n"

            st.markdown(summary_message)

            st.subheader(f"{target_year_ui}年 取得データ一覧")
            
            # --- DataFrame表示用の型変換 ---
            # (N/A を保持したリスト (final_data_ui) を使用)
            display_data = []
            for row in final_data_ui:
                display_row = row.copy() 
                for key, value in display_row.items():
                    if isinstance(value, (int, float)):
                        if key in ['総時間外', '有給消化時間']:
                            display_row[key] = f"{value:,.2f}" # 時間 (xx.xx)
                        elif key in ['有給使用日数', '有給残日数']:
                            display_row[key] = f"{value:,.1f}" # 日数 (x.x)
                        elif key in ['総支給額', '差引支給額']:
                            display_row[key] = f"{value:,.0f}" # 金額
                        else:
                            display_row[key] = str(value) # その他の数値 (あれば)
                    elif value is None:
                        display_row[key] = "N/A"
                    else:
                        display_row[key] = str(value) # 年月日 または "N/A"
                display_data.append(display_row)
            
            # Streamlit の DataFrame で一覧表示
            st.dataframe(display_data) 
        
        else:
            # データが0件だった場合
            st.info(f"{target_year_ui}年のデータは 0件 でした。")
        
        # --- その他の処理年 (UI表示) ---
        other_years_data = result_data.get("other_years_data", {})
        if other_years_data:
            st.subheader("--- その他の処理年 (CSV更新済み) ---")
            
            # 4列で表示
            cols = st.columns(4)
            col_index = 0
            for year, count in other_years_data.items():
                if col_index < len(cols): # カラム数を超えないように
                    cols[col_index].metric(label=f"{year}年", value=f"{count} 件")
                    col_index += 1