# --- csv_handler.py (V6.0) ---
# (新規作成)
# 役割: CSVファイルの読み込み・書き込みを担当する

import logging
import os
import csv
import re 
from datetime import datetime 

logger = logging.getLogger(__name__)

def _safe_convert_to_float(value_str, default_val=0.0):
    """ (V5.0) CSV読み込み用の数値変換ヘルパー """
    if value_str == 'N/A' or value_str is None:
        return "N/A"
    try:
        # V5.0以前の "日" が含まれる形式にも対応
        legacy_str = str(value_str).replace('日', '').strip()
        return float(legacy_str)
    except (ValueError, TypeError):
        return "N/A"

def load_existing_csv(csv_path):
    """ (V5.0) 全期間CSVを読み込む 
        # (変更前) V6.1: csv_path は core/output/... の絶対パス
        # (変更後) V6.1: csv_path は project/output/... の絶対パス
    """
    if not os.path.exists(csv_path):
        logger.info(f"load_existing_csv: 全期間CSVファイルが見つかりません (新規作成): {csv_path}")
        return [], set() 
        
    data_list = []
    existing_dates = set() 
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # V6.0: キー定義をここに集約
            int_keys = ['総支給額', '差引支給額']
            float_keys = ['総時間外', '有給消化時間', '有給使用日数', '有給残日数']
            
            for row in reader:
                # 整数に変換 (失敗時は 0)
                for key in int_keys:
                    try: 
                        row[key] = int(row[key].replace(',', ''))
                    except (ValueError, TypeError, AttributeError): 
                        row[key] = 0
                
                # 浮動小数点数または "N/A" に変換
                for key in float_keys:
                    # '残有給日数' は V5.0 より前の互換キー
                    legacy_val = row.get(key, row.get('残有給日数'))
                    row[key] = _safe_convert_to_float(legacy_val, default_val="N/A")

                data_list.append(row)
                
                # 既得セットの作成
                date_str = row.get('年月日') 
                if date_str and len(date_str) >= 8:
                    existing_dates.add(date_str[0:8])
                    
        logger.info(f"load_existing_csv (V6.0): {len(data_list)} 件の既存データをCSVから読み込みました。")
        logger.info(f"load_existing_csv (V6.0): {len(existing_dates)} 件の既得年月(B)セットを作成しました。({csv_path})")
        return data_list, existing_dates
        
    except Exception as e:
        logger.error(f"load_existing_csv (V6.0): CSV読み込みエラー: {e}", exc_info=True)
        # エラー時は空リストを返し、処理を継続させる (V5.0の動作を踏襲)
        return [], set()

def get_csv_headers():
    """ (V6.0) CSVヘッダーの定義 """
    return [
        '年月日', '総支給額', '差引支給額', 
        '総時間外', '有給消化時間', 
        '有給使用日数', '有給残日数'
    ]

def _sort_key_for_csv(item):
    """ (V6.0) CSV保存時のソートキー """
    date_str = item.get('年月日', '')
    match = re.search(r'(令和\d+年\d+月)', date_str)
    if match:
        try:
            reiwa_str = match.group(1)
            year_match = re.search(r'令和(\d+)年', reiwa_str)
            month_match = re.search(r'年(\d+)月', reiwa_str)
            if year_match and month_match:
                year_val = int(year_match.group(1))
                year = year_val + 2018 
                month = int(month_match.group(1))
                return datetime(year, month, 1)
        except Exception as e_sort:
            logger.warning(f"ソートキーの変換に失敗: {date_str} ({e_sort})")
    return datetime.min # パース失敗時は先頭に来るようにする

def save_to_csv(data_list, root_dir, csv_filename):
    """ (V5.0) 全期間CSV (ソート済み) を保存
        # (変更前) V6.1: root_dir は app.py の場所 (core)
        # (変更後) V6.1: root_dir はプロジェクトのルート (output フォルダがある場所) を受け取る
    """
    if not data_list:
        logger.warning(f"save_to_csv (V6.0): データが0件のため、CSVは作成しませんでした。")
        return None
        
    # V6.1: (変更前) core/output に保存
    # V6.1: (変更後) project/output に保存
    output_dir = os.path.join(root_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    csv_filename_abs = os.path.join(output_dir, csv_filename)
    # V6.1: 相対パス (app.py から見たパス)
    csv_relative_path = os.path.join("output", csv_filename)
    logger.info(f"CSV保存先: {csv_filename_abs}")
    
    headers = get_csv_headers()

    try:
        # 年月日をキーにソート
        sorted_data_list = sorted(data_list, key=_sort_key_for_csv)
        
        with open(csv_filename_abs, 'w', newline='', encoding='utf-8-sig') as f:
            # V6.0: extrasaction='ignore' でヘッダーにないキーは無視する
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore') 
            writer.writeheader()
            writer.writerows(sorted_data_list)
            
        logger.info(f"CSVファイルの書き込みに成功しました。({len(sorted_data_list)} 件)")
        return csv_relative_path
        
    except IOError as e: 
        logger.error(f"CSV書き込みエラー: {e}", exc_info=True)
        return None
    except Exception as e: 
        logger.error(f"CSV処理エラー: {e}", exc_info=True)
        return None