# --- csv_handler.py ---
# 役割: CSVファイルの読み込み・書き込みを担当する

import logging
import os
import csv
import re 
from datetime import datetime 
from typing import List, Set, Tuple, Dict, Any, Union, Optional

logger = logging.getLogger(__name__)

def _safe_convert_to_float(value_str: Any, default_val: str = "N/A") -> Union[float, str]:
    """
    CSV読み込み用の数値変換ヘルパー。
    文字列をfloatに変換する。"N/A"やNoneは"N/A"として返す。
    過去バージョン (V5.0以前) の "X日" という文字列にも対応する。

    Args:
        value_str (Any): 変換対象の文字列 (または数値やNone)。
        default_val (str, optional): 変換失敗時のデフォルト値。

    Returns:
        Union[float, str]: 変換後のfloat、または"N/A"文字列。
    """
    if value_str == 'N/A' or value_str is None:
        return "N/A"
    try:
        # "日" が含まれる形式に対応
        legacy_str = str(value_str).replace('日', '').strip()
        return float(legacy_str)
    except (ValueError, TypeError):
        return default_val

def load_existing_csv(csv_path: str) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    指定されたパスから全期間CSVを読み込む。
    CSVファイルが存在しない場合は、空のリストとセットを返す。

    Args:
        csv_path (str): 読み込むCSVファイルの絶対パス。

    Returns:
        Tuple[List[Dict[str, Any]], Set[str]]:
            - (0) 読み込んだデータ行のリスト (辞書形式)。数値は変換済み。
            - (1) 既存データの年月プレフィックス (例: "令和05年03月") のセット。
    """
    if not os.path.exists(csv_path):
        logger.info(f"load_existing_csv: 全期間CSVファイルが見つかりません (新規作成): {csv_path}")
        return [], set() 
        
    data_list: List[Dict[str, Any]] = []
    existing_dates: Set[str] = set() 
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            int_keys = ['総支給額', '差引支給額']
            float_keys = ['総時間外', '有給消化時間', '有給使用日数', '有給残日数']
            
            for row in reader:
                # 整数に変換 (失敗時は 0)
                for key in int_keys:
                    try: 
                        row[key] = int(str(row.get(key, 0)).replace(',', ''))
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
                    # "令和05年03月度給与" -> "令和05年03月"
                    existing_dates.add(date_str[0:8])
                    
        logger.info(f"load_existing_csv: {len(data_list)} 件の既存データをCSVから読み込みました。")
        logger.info(f"load_existing_csv: {len(existing_dates)} 件の既得年月(B)セットを作成しました。({csv_path})")
        return data_list, existing_dates
        
    except Exception as e:
        logger.error(f"load_existing_csv: CSV読み込みエラー: {e}", exc_info=True)
        # エラー時は空リストを返し、処理を継続させる
        return [], set()

def get_csv_headers() -> List[str]:
    """
    CSVファイルに書き込む際のヘッダーリストを定義する。

    Returns:
        List[str]: CSVヘッダーのリスト。
    """
    return [
        '年月日', '総支給額', '差引支給額', 
        '総時間外', '有給消化時間', 
        '有給使用日数', '有給残日数'
    ]

def _sort_key_for_csv(item: Dict[str, Any]) -> datetime:
    """
    CSV保存時にデータを日付順にソートするためのキーを生成する。
    "令和XX年YY月" の文字列を datetime オブジェクトに変換する。

    Args:
        item (Dict[str, Any]): CSVの1行に相当する辞書。 '年月日' キーを持つ想定。

    Returns:
        datetime: ソートに使用する datetime オブジェクト。パース失敗時は datetime.min。
    """
    date_str = item.get('年月日', '')
    match = re.search(r'(令和\d+年\d+月)', date_str)
    if match:
        try:
            reiwa_str = match.group(1)
            year_match = re.search(r'令和(\d+)年', reiwa_str)
            month_match = re.search(r'年(\d+)月', reiwa_str)
            if year_match and month_match:
                year_val = int(year_match.group(1))
                year = year_val + 2018 # 令和から西暦へ変換
                month = int(month_match.group(1))
                return datetime(year, month, 1)
        except Exception as e_sort:
            logger.warning(f"ソートキーの変換に失敗: {date_str} ({e_sort})")
    # パース失敗時はリストの先頭に来るようにする
    return datetime.min 

def save_to_csv(data_list: List[Dict[str, Any]], root_dir: str, csv_filename: str) -> Optional[str]:
    """
    全期間データをCSVファイルとして保存する。
    保存前に `_sort_key_for_csv` を使って日付順にソートする。

    Args:
        data_list (List[Dict[str, Any]]): 保存するデータのリスト。
        root_dir (str): プロジェクトのルートディレクトリパス (output フォルダの親)。
        csv_filename (str): 保存するCSVファイル名 (例: "data.csv")。

    Returns:
        Optional[str]:
            保存に成功した場合、UI表示用の相対パス (例: "output/data.csv")。
            失敗した場合は None。
    """
    if not data_list:
        logger.warning(f"save_to_csv: データが0件のため、CSVは作成しませんでした。")
        return None
        
    # 保存先: <root_dir>/output/<csv_filename>
    output_dir = os.path.join(root_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    csv_filename_abs = os.path.join(output_dir, csv_filename)
    # UI表示用の相対パス
    csv_relative_path = os.path.join("output", csv_filename)
    logger.info(f"CSV保存先: {csv_filename_abs}")
    
    headers = get_csv_headers()

    try:
        # 年月日をキーにソート
        sorted_data_list = sorted(data_list, key=_sort_key_for_csv)
        
        with open(csv_filename_abs, 'w', newline='', encoding='utf-8-sig') as f:
            # extrasaction='ignore' で、CSVヘッダーにないキーがデータに含まれていても無視する
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore') 
            writer.writeheader()
            writer.writerows(sorted_data_list)
            
        logger.info(f"CSVファイルの書き込みに成功しました。({len(sorted_data_list)} 件)")
        return csv_relative_path
        
    except IOError as e: 
        logger.error(f"CSV書き込みIOエラー: {e}", exc_info=True)
        return None
    except Exception as e: 
        logger.error(f"CSV処理エラー: {e}", exc_info=True)
        return None