# --- main_controller.py ---
# 役割: UI (app.py) から呼び出され、全体の処理フローを制御する
# 1. 処理対象月リストの生成
# 2. 既存CSVの読み込み
# 3. 取得すべき差分年月の計算
# 4. ネットワーク処理 (network_handler) の呼び出し
# 5. .env への資格情報保存 (暗号化)
# 6. 新規データと既存データのマージ、CSV保存 (csv_handler)
# 7. サマリー計算 (summary_calculator)
# 8. app.py への結果返却

import logging
import os
import datetime
from typing import Tuple, Dict, Any

# --- 分割したモジュールをインポート ---
try:
    from date_utils import generate_target_months, generate_target_months_for_full_scan
    from csv_handler import load_existing_csv, save_to_csv, _sort_key_for_csv
    from summary_calculator import calculate_rekigun_summary, calculate_nendo_overtime
    from network_handler import run_automation
    from dotenv import set_key # .env の安全な更新のため
    from encryption_utils import encrypt, CRYPTOGRAPHY_AVAILABLE # 暗号化のため
except ImportError as e:
    logging.critical(f"モジュールのインポートに失敗しました: {e}")
    # このエラーは app.py 側でキャッチされ、UIに表示される
    raise

logger = logging.getLogger(__name__)

# 全期間を保存するCSVファイル名を定義
CSV_FILENAME = "年間サマリー_全期間.csv"

def run_main_logic(
    login_id: str, 
    password: str, 
    ui_target_year: int, 
    run_mode_is_full_scan: bool, 
    root_dir: str, 
    env_path: str, 
    status_placeholder: Any
) -> Tuple[bool, Dict[str, Any]]:
    """
    メインロジック。app.py (Streamlit UI) から呼び出される。
    
    Args:
        login_id (str): ユーザーが入力したログインID。
        password (str): ユーザーが入力したパスワード。
        ui_target_year (int): ユーザーがUIで指定した西暦年。
        run_mode_is_full_scan (bool): 「全期間スキャン」が押されたか (True) / 「実行」か (False)。
        root_dir (str): プロジェクトのルートディレクトリパス (output フォルダがある場所)。
        env_path (str): .env ファイルの絶対パス (ID/PW保存用)。
        status_placeholder (Any): Streamlit の st.empty() オブジェクト (UIステータス更新用)。

    Returns:
        Tuple[bool, Dict[str, Any]]:
            - (0) 処理が成功したか (True) / 失敗したか (False)。
            - (1) 処理結果の辞書。
                  成功時: {"csv_path": str, "final_data_ui": list, ...}
                  失敗時: {"error": str}
                  警告時: {"warning": str}
    """
    
    today = datetime.date.today()
    
    # --- 1. 対象月リスト(A)の作成 ---
    # (A) = Webから取得「すべき」年月のリスト
    if not run_mode_is_full_scan:
        logger.info(f"「実行 (指定年)」モード。ID: {login_id[:4]}***, UI指定年: {ui_target_year}")
        required_months_set = generate_target_months(today, ui_target_year)
        run_mode_message = f"(指定年: {ui_target_year})"
    else:
        logger.info(f"「全期間スキャン」モード。ID: {login_id[:4]}***, UI指定年: {ui_target_year} (サマリー表示用)")
        required_months_set = generate_target_months_for_full_scan(today) 
        run_mode_message = "(全期間スキャン)"
    
    logging.info(f"{run_mode_message}: 取得対象リスト(A) ({len(required_months_set)}件) を作成しました。")
    
    # 取得対象(A)が含まれる「年」のセットを作成 (network_handler を呼び出す単位)
    target_years_to_run = set()
    for reiwa_prefix in required_months_set: 
        try:
            reiwa_num = int(reiwa_prefix[2:4])
            year = reiwa_num + 2018 # 令和 -> 西暦
            target_years_to_run.add(year)
        except Exception: pass
    
    if not target_years_to_run:
        logging.warning("処理対象年が0件です。")
        status_placeholder.warning("処理対象期間のデータが見つかりませんでした。")
        # 処理対象がなくても、既存データのサマリー表示は試みる
        target_years_to_run = set() # 空のセットとして継続
    
    logging.info(f"{run_mode_message}: 処理対象年 (計算結果): {sorted(list(target_years_to_run))}")

    # --- 2. 既存CSVの読み込み ---
    
    all_existing_data = []
    all_existing_dates_set = set()
    
    # (B) = 既存CSVに「既に保存されている」年月のリスト
    csv_path_rel = os.path.join("output", CSV_FILENAME)
    csv_path_abs = os.path.join(root_dir, csv_path_rel)
    
    try:
        all_existing_data, all_existing_dates_set = load_existing_csv(csv_path_abs) 
    except Exception as e_load:
        logging.error(f"全期間CSVの読み込みに失敗しました: {e_load}", exc_info=True)
        return (False, {"error": f"全期間CSV ({csv_path_rel}) の読み込みに失敗しました。\n{e_load}"})
    
    logging.info(f"全CSVから既得日付リスト(B) 合計: {len(all_existing_dates_set)} 件")

    # --- 3. 差分(C)の計算 ---
    # (C) = (A) - (B) = 今回「本当にWebから取得」する年月のリスト
    final_target_dates_set = required_months_set - all_existing_dates_set
    
    logging.info(f"Set演算 (A-B): {len(required_months_set)}(A) - {len(all_existing_dates_set)}(B) = {len(final_target_dates_set)}(C)")

    if not final_target_dates_set:
        status_placeholder.success("データは既に最新の状態でした。HTTP処理をスキップしました。")
        logging.info("取得対象の差分データ(C)が0件のため、HTTP処理をスキップします。")
        
    else:
        # --- 4. ネットワーク処理 (差分がある場合) ---
        status_placeholder.info(f"{run_mode_message}: {len(final_target_dates_set)} 件の新規データを取得します...")
        
        all_new_data_list = []
        http_success = True
        http_message = ""
        
        # 処理対象年ごとに network_handler を呼び出す
        for year_to_run in sorted(list(target_years_to_run)):
            
            # (network_handler は、渡された差分セット(C)と年(year_to_run)を見て、
            # 該当するデータのみを取得する)
            success, message, new_data_list_loop = run_automation(
                login_id=login_id, 
                password=password, 
                target_year=year_to_run, 
                root_dir=root_dir, 
                final_target_dates_set=final_target_dates_set
            )

            if not success:
                http_success = False
                http_message = message
                logging.error(f"{year_to_run}年の処理中にエラーが発生しました: {message}")
                break # エラーが発生したら、以降の年の処理は中断
            
            if new_data_list_loop:
                logging.info(f"{year_to_run}年: {len(new_data_list_loop)} 件の新規データを取得しました。")
                all_new_data_list.extend(new_data_list_loop)
        
        # --- 5. ネットワーク処理結果の判定 ---
        if http_success:
            status_placeholder.success(f"データ取得が完了しました！ (全対象年で新規 {len(all_new_data_list)} 件)")
            
            # --- .env 保存 (暗号化) ---
            try:
                # ログイン成功時のみ、ID/PWを .env に保存（上書き）する
                encrypted_id = encrypt(login_id)
                encrypted_pw = encrypt(password)
                
                # python-dotenv の set_key で .env ファイルを安全に更新
                set_key(env_path, "MY_LOGIN_ID", encrypted_id)
                set_key(env_path, "MY_PASSWORD", encrypted_pw)
                
                if CRYPTOGRAPHY_AVAILABLE:
                    logging.info(f"ログイン成功。.env ファイルに「暗号化」して保存しました: {env_path}")
                else:
                    logging.warning(f"ログイン成功。.env ファイルに「平文」で保存しました (cryptography未導入): {env_path}")

            except Exception as e:
                logging.error(f".env ファイルへの保存に失敗しました: {e}", exc_info=True)
                # .env保存失敗は致命的ではないため、警告としてUIに返す
                return (True, {"warning": f".env ファイルへの保存に失敗しました: {e}"})

            # --- 6. CSVへのマージと保存 ---
            all_existing_data.extend(all_new_data_list)
            logging.info(f"全 {len(all_new_data_list)} 件の新規データを既存リスト (現在 {len(all_existing_data)} 件) にマージしました。")

            logging.info(f"全期間CSVを保存中... (合計 {len(all_existing_data)} 件)")
            
            csv_path_result = save_to_csv(all_existing_data, root_dir, CSV_FILENAME)
                    
            if not csv_path_result:
                logging.error(f"全期間CSV ({CSV_FILENAME}) の保存に失敗しました。")
                return (False, {"error": f"全期間CSV ({CSV_FILENAME}) の保存に失敗しました。"})
        
        else:
            # HTTPエラー
            logging.error(f"HTTP処理が失敗しました: {http_message}")
            status_placeholder.error(f"エラーが発生しました:\n{http_message}")
            return (False, {"error": http_message})
    
    # --- 7. 最終サマリーの計算 ---
    # (HTTP処理をスキップした場合も、ここに来る)
    
    logging.info(f"UI指定年 ({ui_target_year}年) のサマリー計算を開始します。")
    
    # 全期間データ (all_existing_data) から、UI指定年のデータ (final_data_ui) を抽出
    reiwa_year_ui = ui_target_year - 2018
    target_reiwa_year_str = f"令和{reiwa_year_ui:02d}年"
    
    final_data_ui = []
    for item in all_existing_data:
        date_str = item.get("年月日", "")
        if target_reiwa_year_str in date_str:
            final_data_ui.append(item)
    
    # UI表示用に、日付順でソートする
    try:
        final_data_ui.sort(key=_sort_key_for_csv)
    except Exception as e_sort_ui:
        logging.warning(f"UIデータ抽出後のソートに失敗 (無視します): {e_sort_ui}")

    
    summary_data_rekigun = {}
    summary_nendo_overtime = 0.0
    
    if final_data_ui:
        # サマリー計算用の前処理
        # (N/A を 0.0 に変換する)
        calc_data_list = []
        keys_to_convert = [
            '総支給額', '差引支給額', '総時間外', 
            '有給消化時間', '有給使用日数', '有給残日数'
        ]
        
        for item in final_data_ui:
            calc_item = item.copy()
            for key in keys_to_convert:
                val = calc_item.get(key)
                if not isinstance(val, (int, float)):
                    calc_item[key] = 0.0 # N/A や文字列を 0.0 に変換
            calc_data_list.append(calc_item)

        # 暦年サマリーの計算
        summary_data_rekigun = calculate_rekigun_summary(calc_data_list)
        
        # 最新月の有給情報は、N/A を保持したオリジナルのリスト (final_data_ui) から取得し直す
        latest_item_original = final_data_ui[-1]
        summary_data_rekigun['latest_paid_leave_time'] = latest_item_original.get('有給消化時間', 'N/A')
        summary_data_rekigun['latest_paid_leave_used_days'] = latest_item_original.get('有給使用日数', 'N/A')
        summary_data_rekigun['latest_paid_leave_remaining_days'] = latest_item_original.get('有給残日数', 'N/A')

        # 年度時間外の計算 (全期間データ all_existing_data を渡す)
        summary_nendo_overtime = calculate_nendo_overtime(all_existing_data, ui_target_year)
    
    else:
        logging.info(f"{ui_target_year}年 のデータは 0件 でした。")
        # 0件でも年度時間外の計算は試みる (前年3月など、UI指定年以外のデータが使われるため)
        summary_nendo_overtime = calculate_nendo_overtime(all_existing_data, ui_target_year)


    # --- 8. その他の処理年 (UI表示用) ---
    # (「全期間スキャン」実行時、UI指定年以外の年も処理された場合)
    other_years_data = {}
    other_years_processed = {y for y in target_years_to_run if y != ui_target_year}
    
    if other_years_processed:
        for other_year in sorted(list(other_years_processed)):
            reiwa_year_other = other_year - 2018
            target_reiwa_year_str_other = f"令和{reiwa_year_other:02d}年"
            other_data_count = 0
            for item in all_existing_data:
                 if target_reiwa_year_str_other in item.get("年月日", ""):
                     other_data_count += 1
            other_years_data[other_year] = other_data_count

    # --- 9. 成功時の戻り値を作成 ---
    
    success_result = {
        "csv_path": csv_path_rel, # "output/..." の相対パス
        "ui_target_year": ui_target_year,
        "final_data_ui": final_data_ui, # UI表示用のデータ (N/A 保持)
        "summary_data_rekigun": summary_data_rekigun, # 暦年集計
        "summary_nendo_overtime": summary_nendo_overtime, # 年度時間外
        "other_years_data": other_years_data # その他の年
    }
    
    return (True, success_result)