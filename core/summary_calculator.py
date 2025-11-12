# --- summary_calculator.py (V6.0) ---
# (新規作成)
# 役割: 読み込んだデータリストに基づき、サマリー（集計）を行う

import logging
import re

logger = logging.getLogger(__name__)

def _parse_year_month_from_date_str(date_str):
    """ (V5.0) 年月日文字列から (西暦, 月) を抽出 """
    if not date_str:
        return None
    year_match = re.search(r'令和(\d+)年', date_str)
    month_match = re.search(r'年(\d+)月', date_str)
    if year_match and month_match:
        try:
            reiwa_year = int(year_match.group(1))
            year = reiwa_year + 2018
            month = int(month_match.group(1))
            return (year, month)
        except (ValueError, TypeError):
            pass
    logger.warning(f"_parse_year_month_from_date_str: パース失敗: {date_str}")
    return None

def _sum_safe(items):
    """ (V6.0) 数値 (int/float) のみを合計する (N/A や文字列を無視) """
    total = 0
    for item in items:
        if isinstance(item, (int, float)):
            total += item
    return total

def calculate_rekigun_summary(data_list_for_year):
    """ (V5.0) 暦年 (1-12月) の集計 """
    
    # V6.0: デフォルトの戻り値を定義
    default_summary = {
        "total_pay": 0, "total_net_pay": 0, "total_overtime": 0.0, 
        "latest_paid_leave_time": "N/A",
        "latest_paid_leave_used_days": "N/A",
        "latest_paid_leave_remaining_days": "N/A"
    }
    
    if not data_list_for_year:
        logger.info("calculate_rekigun_summary: 対象データが0件のため、デフォルト値を返します。")
        return default_summary

    # --- V6.0: 集計 (N/A を無視) ---
    total_pay = _sum_safe(item.get('総支給額', 0) for item in data_list_for_year)
    total_net_pay = _sum_safe(item.get('差引支給額', 0) for item in data_list_for_year)
    total_overtime = _sum_safe(item.get('総時間外', 0) for item in data_list_for_year)
    
    # --- V6.0: 最新月の情報取得 (V5.0の動作を踏襲) ---
    # (data_list_for_year は既にソート済みであることを前提とする)
    latest_item = data_list_for_year[-1]
    latest_paid_leave_time = latest_item.get('有給消化時間', 'N/A')
    latest_paid_leave_used_days = latest_item.get('有給使用日数', 'N/A')
    latest_paid_leave_remaining_days = latest_item.get('有給残日数', 'N/A')

    summary_data = {
        "total_pay": total_pay, 
        "total_net_pay": total_net_pay, 
        "total_overtime": total_overtime, 
        "latest_paid_leave_time": latest_paid_leave_time,
        "latest_paid_leave_used_days": latest_paid_leave_used_days,
        "latest_paid_leave_remaining_days": latest_paid_leave_remaining_days
    }
    logger.info(f"暦年サマリー計算完了 (対象 {len(data_list_for_year)} 件): {summary_data}")
    return summary_data

def calculate_nendo_overtime(all_data_list, target_rekigun_year):
    """ (V5.0) 年度 (4月～翌3月) の時間外合計を計算 """
    nendo_overtime_total = 0.0
    
    if not all_data_list:
        return 0.0
        
    nendo_start_year = target_rekigun_year
    nendo_end_year = target_rekigun_year + 1
    
    logger.info(f"calculate_nendo_overtime: {nendo_start_year}年度 ( {nendo_start_year}/4～{nendo_end_year}/3 ) の集計を開始...")

    for item in all_data_list:
        date_str = item.get('年月日', '') 
        parsed_date = _parse_year_month_from_date_str(date_str)
        if not parsed_date:
            continue
        year, month = parsed_date

        overtime = item.get('総時間外', 0)
        # V6.0: _sum_safe と同様のロジック
        if not isinstance(overtime, (int, float)): 
            overtime = 0.0

        if year == nendo_start_year and (4 <= month <= 12):
            nendo_overtime_total += overtime
        elif year == nendo_end_year and (1 <= month <= 3):
            nendo_overtime_total += overtime
            
    logger.info(f"calculate_nendo_overtime: {nendo_start_year}年度 ( {nendo_start_year}/4～{nendo_end_year}/3 ) 集計完了: {nendo_overtime_total:.2f} 時間")
    return nendo_overtime_total