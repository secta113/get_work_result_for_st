# --- network_handler.py ---
# 役割: requestsによる通信、HTMLのパースを担当する

import logging
import os
import re 
from urllib.parse import urlparse, parse_qs, unquote_plus
from typing import Set, Dict, Any, Tuple, List, Optional

try:
    import requests
    from requests.sessions import Session
    from requests.models import Response
    from bs4 import BeautifulSoup
except ImportError:
    logging.critical("必須ライブラリ (requests, beautifulsoup4) が見つかりません。")
    raise

logger = logging.getLogger(__name__)

# --- 定義 ---
BASE_URL = "https://meisai.palma-svc.co.jp/users"

# .env からカンパニーコードを読み込む (app.py で load_dotenv 済み)
COMPANY_CODE = os.getenv("LOGIN_COMPANY_CODE", "witesi") # デフォルト値 "witesi"
if COMPANY_CODE == "witesi" and not os.getenv("LOGIN_COMPANY_CODE"):
    logger.warning("LOGIN_COMPANY_CODE が .env に設定されていません。デフォルト値 'witesi' を使用します。")
elif not COMPANY_CODE:
     logger.error("LOGIN_COMPANY_CODE が .env に設定されていますが、値が空です。フォールバックします。")
     COMPANY_CODE = "witesi" 

LOGIN_PAGE_URL = f"{BASE_URL}/Login.aspx?c={COMPANY_CODE}"
MENU_PAGE_URL = f"{BASE_URL}/PMenu.aspx"
LIST_PAGE_URL = f"{BASE_URL}/PShowSB.aspx"
DETAIL_PAGE_URL = f"{BASE_URL}/PShowSBDetail.aspx"

# ネットワークログのパス (グローバル変数)
DEBUG_LOG_PATH = "" 

# ===============================================
# ▼▼▼ ネットワークログ保存 ▼▼▼
# ===============================================

def initialize_requests_logger(root_dir: str) -> None:
    """
    ネットワークログ (debug_requests_network_log.txt) を初期化する。
    <root_dir>/output/ にログファイルを生成（上書き）する。

    Args:
        root_dir (str): プロジェクトのルートディレクトリパス (output フォルダの親)。
    """
    global DEBUG_LOG_PATH
    output_dir = os.path.join(root_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    DEBUG_LOG_PATH = os.path.join(output_dir, "debug_requests_network_log.txt")
    
    try:
        with open(DEBUG_LOG_PATH, "w", encoding="utf-8") as f:
            f.write("--- requests ネットワークログ (V-ReqDebug) ---\n")
            f.write("===============================================\n\n")
        logger.info(f"--- V-ReqDebug: requests ログを {DEBUG_LOG_PATH} に保存します ---")
    except Exception as e:
        logger.error(f"--- V-ReqDebug: ログファイルの初期化に失敗: {e} ---")

def log_requests_call(step_name: str, response_object: Response) -> None:
    """
    HTTPリクエスト/レスポンスの情報をログファイルに書き込む。

    Args:
        step_name (str): 処理ステップ名 (例: "ステップ1: ログインページ (GET)")。
        response_object (Response): requests のレスポンスオブジェクト。
    """
    if not DEBUG_LOG_PATH:
        logger.warning("V-ReqDebug: ログファイルが初期化されていません。")
        return
    try:
        req = response_object.request 
        resp = response_object       
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"--- {step_name} ---\n")
            f.write(f"Method: {req.method}\n")
            f.write(f"URL: {req.url}\n")
            
            f.write("\n[リクエスト ヘッダー (requests が送信)]\n")
            for h_name, h_val in req.headers.items():
                if h_name.lower() not in ['cookie']: # Cookie はログアウト
                    f.write(f"  {h_name}: {h_val}\n")
            
            if req.method == 'POST' and req.body:
                try:
                    # POSTデータをデコードして見やすくする
                    body_str = unquote_plus(req.body, encoding='utf-8')
                    f.write("\n[POST ペイロード (Form Data)]\n")
                    parsed_body = parse_qs(body_str)
                    for key, val_list in parsed_body.items():
                        val = val_list[0] if val_list else ""
                        # VIEWSTATE などは長すぎるので省略
                        if "__VIEWSTATE" in key or "__EVENTVALIDATION" in key:
                            f.write(f"  {key}: {val[:50]}... (省略)\n")
                        else:
                            f.write(f"  {key}: {val}\n")
                except Exception as e_body:
                    f.write(f"\n[POST ペイロードのデコード失敗]: {e_body}\n")
            
            f.write(f"\n[レスポンス]\n")
            f.write(f"  Status Code: {resp.status_code}\n")
            f.write(f"  Reason: {resp.reason}\n")
            
            # リダイレクト履歴
            if resp.history:
                f.write(f"  History (Redirects):\n")
                for i, hist_resp in enumerate(resp.history):
                    f.write(f"    [{i}] {hist_resp.status_code} -> {hist_resp.headers.get('Location')}\n")
                f.write(f"    [Final] {resp.status_code} (URL: {resp.url})\n")
            
            f.write("\n[レスポンス ヘッダー]\n")
            for h_name, h_val in resp.headers.items():
                if h_name.lower() in ['location', 'set-cookie']: # 重要なヘッダー
                    f.write(f"  >>>> {h_name}: {h_val}\n")
                else:
                    f.write(f"  {h_name}: {h_val}\n")
            f.write("\n===============================================\n\n")
    except Exception as e:
        logger.error(f"--- V-ReqDebug: ログの書き込み中にエラー: {e} ---")

# ===============================================
# ▼▼▼ ASP.NET ヘルパー ▼▼▼
# ===============================================

def get_aspnet_form_data(soup: BeautifulSoup) -> Dict[str, str]:
    """
    ASP.NET の WebForm で使用される必須フォーム項目
    (__VIEWSTATE, __EVENTVALIDATION, __VIEWSTATEGENERATOR) を
    BeautifulSoup オブジェクトから抽出する。

    Args:
        soup (BeautifulSoup): パース対象の BeautifulSoup オブジェクト (HTMLページ)。

    Returns:
        Dict[str, str]: 抽出したフォームデータを格納した辞書。
                        見つからない場合は空文字が設定される。
    """
    try:
        viewstate = soup.find('input', {'name': '__VIEWSTATE'}).get('value', '')
        event_validation = soup.find('input', {'name': '__EVENTVALIDATION'}).get('value', '')
        
        # __VIEWSTATEGENERATOR は存在しないページもあるため、存在チェックを行う
        viewstate_generator_input = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        viewstate_generator = viewstate_generator_input.get('value', '') if viewstate_generator_input else ""
        
        return {
            "__VIEWSTATE": viewstate, 
            "__EVENTVALIDATION": event_validation, 
            "__VIEWSTATEGENERATOR": viewstate_generator
        }
    except Exception as e:
        # 主に find の対象 (input) が None の場合に AttributeError が発生する
        logger.warning(f"get_aspnet_form_data: __VIEWSTATE等の取得に失敗: {e}")
        return {"__VIEWSTATE": "", "__EVENTVALIDATION": "", "__VIEWSTATEGENERATOR": ""}

def get_timestamp_from_url(url: str) -> Optional[str]:
    """
    URLのクエリパラメータから 'timestamp' の値を取得する。

    Args:
        url (str): 対象のURL (例: "PMenu.aspx?timestamp=123456")。

    Returns:
        Optional[str]: 
            抽出した timestamp の値。見つからない場合は None。
    """
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        timestamp = query_params.get('timestamp', [None])[0]
        if timestamp:
            logger.debug(f"get_timestamp_from_url: URLから timestamp ({timestamp}) を取得しました。")
            return timestamp
    except Exception as e:
        logger.warning(f"get_timestamp_from_url: URLからのtimestamp取得に失敗: {e}")
    
    logger.warning("get_timestamp_from_url: timestampが取得できませんでした。")
    return None

# ===============================================
# ▼▼▼ HTMLパース ▼▼▼
# ===============================================

def parse_payslip_detail(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    給与明細詳細ページのHTML (soup) から、必要な項目
    (総支給額, 差引支給額, 時間外, 有給関連) を抽出する。
    
    Notes:
        HTML上の表記「有休」を、CSV/サマリー側のキー「有給」にマッピングする。

    Args:
        soup (BeautifulSoup): パース対象の BeautifulSoup オブジェクト (詳細ページ)。

    Returns:
        Dict[str, Any]: 抽出したデータを格納した辞書。
                        見つからない項目は "N/A" が設定される。
    """
    detail_data = {
        "総支給額": "N/A", "差引支給額": "N/A",
        "総時間外": "N/A", "有給消化時間": "N/A",
        "有給使用日数": "N/A", # CSV/サマリー側のキー (有給)
        "有給残日数": "N/A"   # CSV/サマリー側のキー (有給)
    }
    
    try:
        html_div = soup.find('div', id='Html')
        if not html_div:
            logger.warning("parse_payslip_detail: <div id='Html'> が見つかりませんでした。")
            return detail_data
            
        # <dl> <dt>キー</dt> <dd>値</dd> </dl> の構造をループ
        for dl in html_div.find_all('dl'):
            dt = dl.find('dt')
            dd = dl.find('dd')
            if dt and dd:
                key = dt.get_text(strip=True) # HTML上のキー (例: "有休使用日数")
                value_str = dd.get_text(strip=True).replace(',', '') 
                
                try:
                    # 0.5日 や 0.5時間 を考慮
                    if '.' in value_str: 
                        value_num = float(value_str)
                    else: 
                        value_num = int(value_str)
                except ValueError: 
                    value_num = value_str # 数値変換失敗 (N/Aなど)
                
                if key == '総支給額': detail_data['総支給額'] = value_num
                elif key == '差引支給額': detail_data['差引支給額'] = value_num
                elif key == '総時間外': detail_data['総時間外'] = value_num
                elif key == '有給消化時間': detail_data['有給消化時間'] = value_num
                
                # HTML上の表記 (有休) と CSVキー (有給) のマッピング
                elif key == '有休使用日数': # HTMLの表記
                    detail_data['有給使用日数'] = value_num # CSVキー (有給) に格納
                    logger.info(f"parse_payslip_detail: 「有休使用日数」を取得: {value_num}")
                elif key == '有休残日数': # HTMLの表記
                    detail_data['有給残日数'] = value_num # CSVキー (有給) に格納
                    logger.info(f"parse_payslip_detail: 「有休残日数」を取得: {value_num}")
        
    except Exception as e:
        logger.error(f"parse_payslip_detail: パース中に予期せぬエラー: {e}", exc_info=True)
        # エラーが発生しても、デフォルト値 (N/A) が入った辞書を返す
        
    return detail_data

# ===============================================
# ▼▼▼ メイン実行関数 ▼▼▼
# ===============================================

def run_automation(
    login_id: str, 
    password: str, 
    target_year: int, 
    root_dir: str, 
    final_target_dates_set: Set[str]
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    指定された単一の年 (target_year) について、
    Webサイトにログインし、明細を取得する自動化処理を実行する。
    
    Args:
        login_id (str): ログインID。
        password (str): パスワード。
        target_year (int): 処理対象の西暦年 (例: 2023)。
        root_dir (str): プロジェクトのルートディレクトリ (ログ保存用)。
        final_target_dates_set (Set[str]):
            取得すべき年月の差分セット (C) (例: {"令和05年03月"})。
            このセットに含まれない明細はスキップされる。

    Returns:
        Tuple[bool, str, List[Dict[str, Any]]]:
            - (0) 成功/失敗 (bool)。
            - (1) 処理結果メッセージ (str)。
            - (2) 取得した新規データのリスト (List[Dict])。
    """
    
    logger.info("=====================================")
    logger.info(f"run_automation (requests版) ({target_year}年): 処理を開始します。")
    
    # ネットワークログを初期化
    initialize_requests_logger(root_dir)
    
    new_payslip_data_list: List[Dict[str, Any]] = []
    
    # --- 対象年・対象月の絞り込み ---
    reiwa_year = target_year - 2018
    target_reiwa_year_str = f"令和{reiwa_year:02d}年" 
    logger.info(f"対象年: {target_year}年 ({target_reiwa_year_str})")

    # この年 (target_year) に関連する差分セット(C)のみを抽出
    target_dates_for_this_year = {
        date_prefix for date_prefix in final_target_dates_set 
        if target_reiwa_year_str in date_prefix
    }
    if not target_dates_for_this_year:
        logger.info(f"{target_year}年: 差分リスト(C)が0件のため、HTTP処理をスキップします。")
        return (True, "処理スキップ (対象年データなし)", [])
    
    logger.info(f"{target_year}年: 差分リスト(C)に基づき、最大 {len(target_dates_for_this_year)} 件のデータを取得します。")

    try:
        with requests.Session() as session:
            # --- セッションヘッダー設定 ---
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8", 
                "Origin": "https://meisai.palma-svc.co.jp", 
            })

            # --- ステップ1: ログインページ (GET) ---
            logger.info(f"ステップ1: ログインページにアクセス中... (GET: {LOGIN_PAGE_URL})")
            resp_login_page = session.get(LOGIN_PAGE_URL)
            log_requests_call("ステップ1: ログインページ (GET)", resp_login_page)
            resp_login_page.raise_for_status() # ステータスコードエラーチェック
            soup_login = BeautifulSoup(resp_login_page.text, 'html.parser')
            form_data = get_aspnet_form_data(soup_login)

            # --- ステップ2: ログイン (POST) ---
            login_payload = {
                "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                "__VIEWSTATE": form_data.get("__VIEWSTATE", ""),
                "__EVENTVALIDATION": form_data.get("__EVENTVALIDATION", ""),
                "__VIEWSTATEGENERATOR": form_data.get("__VIEWSTATEGENERATOR", ""),
                "HiddenField1": "JavaScript On!", "CheckWidth": "99999",
                "txtLoginID": login_id, "txtLoginPW": password,
                "cmdSubmit": "ログイン"
            }
            logger.info("ステップ2: ログイン実行中... (POST)")
            resp_menu_page = session.post(LOGIN_PAGE_URL, data=login_payload)
            log_requests_call("ステップ2: ログイン実行 (POST)", resp_menu_page)
            resp_menu_page.raise_for_status() 
            
            # ログイン成功時は PMenu.aspx にリダイレクトされるはず
            if MENU_PAGE_URL not in resp_menu_page.url:
                logger.warning(f"ログイン失敗。リダイレクト先 URL: {resp_menu_page.url}")
                if "PLoginErr" in resp_menu_page.url:
                    return (False, "ログインに失敗しました。\nIDまたはパスワードが間違っています。", [])
                return (False, f"ログインに失敗しました。\n予期せぬページに遷移しました: {resp_menu_page.url}", [])
            
            logger.info(f"ログイン成功。メニューページに遷移しました。 URL: {resp_menu_page.url}")
            menu_timestamp = get_timestamp_from_url(resp_menu_page.url)
            soup_menu = BeautifulSoup(resp_menu_page.text, 'html.parser')
            menu_form_data = get_aspnet_form_data(soup_menu)
            menu_url_with_ts = resp_menu_page.url # timestamp 付きのURL

            # --- ステップ3: 一覧ページへ移動 (POST) ---
            list_payload = {
                "__EVENTTARGET": "cmdShowSalary", "__EVENTARGUMENT": "", # 「給与明細書」ボタン
                "__VIEWSTATE": menu_form_data.get("__VIEWSTATE", ""),
                "__EVENTVALIDATION": menu_form_data.get("__EVENTVALIDATION", ""),
                "__VIEWSTATEGENERATOR": menu_form_data.get("__VIEWSTATEGENERATOR", ""),
            }
            logger.info("ステップ3: 「給与明細書」一覧ページに移動中... (POST)")
            resp_list_page = session.post(menu_url_with_ts, data=list_payload, headers={"Referer": menu_url_with_ts})
            log_requests_call("ステップ3: 一覧ページへ移動 (POST)", resp_list_page)
            resp_list_page.raise_for_status()
            
            if LIST_PAGE_URL not in resp_list_page.url:
                logger.warning(f"一覧ページへの遷移失敗。リダイレクト先 URL: {resp_list_page.url}")
                return (False, "「給与明細書」一覧ページへの遷移に失敗しました。", [])

            logger.info(f"ステップ4: 明細一覧ページに遷移成功。 URL: {resp_list_page.url}")
            current_list_soup = BeautifulSoup(resp_list_page.text, 'html.parser')
            current_list_form_data = get_aspnet_form_data(current_list_soup)
            current_list_url = resp_list_page.url
            
            # --- ステップ5: 対象明細の検索 ---
            logger.info(f"ステップ5: {target_reiwa_year_str} の明細を検索中...")
            table = current_list_soup.find('table', {'id': 'tdb'})
            target_payslips = []
            if table:
                rows = table.find_all('tr')[1:] # ヘッダー行を除く
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) < 3: continue
                    date_text = cells[2].get_text(strip=True) # "令和05年03月度給与"
                    
                    # この年 (target_reiwa_year_str) のみ対象
                    if target_reiwa_year_str in date_text:
                        html_button = cells[1].find('input')
                        if html_button and html_button.get('name'):
                            target_payslips.append({
                                "date": date_text, 
                                "html_button_name": html_button.get('name') # "tdb$ctl02$cmdShowSB" など
                            })
            
            if not target_payslips:
                logger.warning(f"{target_reiwa_year_str} の明細は見つかりませんでした。")
                # この年の処理はスキップ (エラーではない)
                pass
            else:
                logger.info(f"{len(target_payslips)} 件の対象明細が見つかりました (Web上)。差分(C)と比較します...")

                # --- ステップ6: 詳細ループ ---
                for i, payslip in enumerate(target_payslips):
                    date_str = payslip['date']
                    html_button_name = payslip['html_button_name']
                    
                    # "令和05年03月" の形式に
                    date_prefix = date_str[0:8] 
                    
                    # 差分リスト(C) (final_target_dates_set) に含まれないものはスキップ
                    if date_prefix not in final_target_dates_set:
                        logger.debug(f"スキップ (既得): {date_prefix}")
                        continue 
                    
                    log_step_name = f"ステップ6-{(i+1)}: 詳細取得 (ID: {html_button_name})"
                    logger.info(f"{log_step_name} ({date_str}) を取得中... (POST)")
                    
                    detail_payload = {
                        "__EVENTTARGET": html_button_name, "__EVENTARGUMENT": "",
                        "__VIEWSTATE": current_list_form_data.get("__VIEWSTATE"),
                        "__EVENTVALIDATION": current_list_form_data.get("__EVENTVALIDATION"),
                        "__VIEWSTATEGENERATOR": current_list_form_data.get("__VIEWSTATEGENERATOR"),
                    }
                    
                    resp_detail = session.post(current_list_url, data=detail_payload, headers={"Referer": current_list_url})
                    log_requests_call(log_step_name, resp_detail)
                    resp_detail.raise_for_status() 
                    
                    if DETAIL_PAGE_URL not in resp_detail.url:
                        logger.warning(f"詳細ページへの遷移失敗。URL: {resp_detail.url}")
                        # 失敗時は一覧ページに戻ったと仮定してフォームデータを更新
                        current_list_soup = BeautifulSoup(resp_detail.text, 'html.parser')
                        current_list_form_data = get_aspnet_form_data(current_list_soup)
                        current_list_url = resp_detail.url
                        continue # この月の処理をスキップ

                    logger.info(f"  ... 詳細ページ取得完了。 URL: {resp_detail.url}")
                    
                    soup_detail = BeautifulSoup(resp_detail.text, 'html.parser')
                    
                    # 詳細ページからデータをパース
                    extracted_detail = parse_payslip_detail(soup_detail)
                    
                    # CSV保存用のデータ行を作成
                    final_data_row = {
                        "年月日": date_str,
                        "総支給額": extracted_detail.get("総支給額", "N/A"),
                        "差引支給額": extracted_detail.get("差引支給額", "N/A"),
                        "総時間外": extracted_detail.get("総時間外", "N/A"),
                        "有給消化時間": extracted_detail.get("有給消化時間", "N/A"),
                        "有給使用日数": extracted_detail.get("有給使用日数", "N/A"),
                        "有給残日数": extracted_detail.get("有給残日数", "N/A")
                    }
                    new_payslip_data_list.append(final_data_row)
                    logger.info(f"  ... データ取得完了: {final_data_row}")

                    # --- ステップ6-B: 「戻る」ボタン ---
                    log_step_name_back = f"ステップ6-{(i+1)}-B: 「戻る」"
                    logger.info(f"  ... {log_step_name_back} を押して一覧に戻ります...")
                    detail_form_data = get_aspnet_form_data(soup_detail)
                    detail_timestamp = get_timestamp_from_url(resp_detail.url)
                    detail_url = resp_detail.url 
                    
                    go_back_payload = {
                        "__EVENTTARGET": "cmdGoBack", "__EVENTARGUMENT": "",
                        "__VIEWSTATE": detail_form_data.get("__VIEWSTATE"),
                        "__EVENTVALIDATION": detail_form_data.get("__EVENTVALIDATION"),
                        "__VIEWSTATEGENERATOR": detail_form_data.get("__VIEWSTATEGENERATOR"),
                        "timestamp": detail_timestamp, # 戻る際に timestamp が必要な場合がある
                    }
                    
                    resp_back_to_list = session.post(detail_url, data=go_back_payload, headers={"Referer": detail_url})
                    log_requests_call(log_step_name_back, resp_back_to_list)
                    resp_back_to_list.raise_for_status()
                    
                    if LIST_PAGE_URL not in resp_back_to_list.url:
                        logger.error("「戻る」ボタンでの一覧ページへの復帰に失敗しました。")
                        return (False, "詳細ページから一覧ページへの復帰に失敗しました。", [])
                    
                    logger.info(f"  ... 一覧ページに復帰完了。 URL: {resp_back_to_list.url}")
                    
                    # 戻った先（一覧）のフォームデータを次のループのために更新
                    current_list_soup = BeautifulSoup(resp_back_to_list.text, 'html.parser')
                    current_list_form_data = get_aspnet_form_data(current_list_soup)
                    current_list_url = resp_back_to_list.url

            # --- ステップ7: ログアウト ---
            try:
                logout_payload = {
                    "__EVENTTARGET": "cmdLogOut", "__EVENTARGUMENT": "",
                    "__VIEWSTATE": current_list_form_data.get("__VIEWSTATE"),
                    "__EVENTVALIDATION": current_list_form_data.get("__EVENTVALIDATION"),
                    "__VIEWSTATEGENERATOR": current_list_form_data.get("__VIEWSTATEGENERATOR"), 
                }
                logger.info("ステップ7: 処理完了。ログアウトします... (POST)")
                resp_logout = session.post(current_list_url, data=logout_payload, headers={"Referer": current_list_url})
                log_requests_call("ステップ7: ログアウト", resp_logout)
                logger.info(f"ステップ8: ログアウト実行。セッションを終了します。")
            except Exception as e_logout:
                logger.warning(f"ログアウト処理中にエラーが発生しました (無視します): {e_logout}")

        # --- 正常終了 ---
        return (True, "正常に処理が完了しました。", new_payslip_data_list)

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP通信処理中にエラーが発生しました: {e}", exc_info=True)
        return (False, f"HTTP通信処理中にエラーが発生しました:\n{e}", [])
    except Exception as e:
        logger.error(f"処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return (False, f"処理中に予期せぬエラーが発生しました:\n{e}", [])
    
    finally:
        logger.info(f"run_automation ({target_year}年): 処理が終了しました。")
        logger.info("=====================================\n")