# --- date_utils.py (V6.0) ---
# (新規作成)
# 役割: 処理対象月のリスト生成を担当する

import datetime
import logging

logger = logging.getLogger(__name__)

def generate_target_months(today, ui_year):
    """ (V2.5) 指定年ベース (通常実行) """
    target_set = set() 
    
    if ui_year == today.year:
        # (A) 本年の場合
        logger.info(f"generate_target_months: UI指定年={ui_year} (本年) のため、V2.4ロジック（前年3月～）を実行します。")
        end_year = today.year
        end_month = today.month
        if today.day < 12:
            logger.info(f"generate_target_months: 本日({today})が12日未満のため、当月({end_month}月)は対象外とします。")
            if end_month == 1:
                end_year -= 1
                end_month = 12
            else:
                end_month -= 1
        else:
             logger.info(f"generate_target_months: 本日({today})が12日以降のため、当月({end_month}月)を対象に含めます。")
        start_year = today.year - 1
        start_month = 3
    
    else:
        # (B) 本年以外の場合
        logger.info(f"generate_target_months: UI指定年={ui_year} (本年以外) のため、V2.4例外ロジック（指定年の1月～12月）を実行します。")
        start_year = ui_year
        start_month = 1
        end_year = ui_year
        end_month = 12
        
    logger.info(f"generate_target_months: 取得対象期間(A): {start_year}年{start_month}月 ～ {end_year}年{end_month}月")
    
    current_year = start_year
    current_month = start_month
    
    while True:
        if current_year > end_year or (current_year == end_year and current_month > end_month):
            break
        reiwa_year = current_year - 2018
        reiwa_str_prefix = f"令和{reiwa_year:02d}年{current_month:02d}月" 
        target_set.add(reiwa_str_prefix)
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
            
    return target_set

def generate_target_months_for_full_scan(today):
    """ (V4.1) 全期間スキャン用 (2019/1～当月) """
    target_set = set() 
    logger.info("generate_target_months_for_full_scan: 全期間スキャンが実行されました。")
    
    start_year = 2019 
    start_month = 1
    
    end_year = today.year
    end_month = today.month
    if today.day < 12:
        logger.info(f"generate_target_months (全期間): 本日({today})が12日未満のため、当月({end_month}月)は対象外とします。")
        if end_month == 1:
            end_year -= 1
            end_month = 12
        else:
            end_month -= 1
    else:
            logger.info(f"generate_target_months (全期間): 本日({today})が12日以降のため、当月({end_month}月)を対象に含めます。")
    
    logger.info(f"generate_target_months (全期間): 取得対象期間(A): {start_year}年{start_month}月 ～ {end_year}年{end_month}月")
    
    current_year = start_year
    current_month = start_month
    
    while True:
        if current_year > end_year or (current_year == end_year and current_month > end_month):
            break
        reiwa_year = current_year - 2018
        reiwa_str_prefix = f"令和{reiwa_year:02d}年{current_month:02d}月"
        target_set.add(reiwa_str_prefix)
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
            
    return target_set