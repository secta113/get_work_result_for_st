# --- encryption_utils.py (V6.3 マシン固有) ---
# 役割: .env に保存するID/パスワードの暗号化・復号
# V6.3 変更点: PreshareKey を廃止し、MACアドレスをキーとして使用

import base64
import logging
import os
import uuid # ★ V6.3: MACアドレス取得のためインポート

# --- 外部ライブラリ (cryptography) ---
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logging.critical("="*50)
    logging.critical("必須ライブラリ (cryptography) が見つかりません。")
    logging.critical("pip install cryptography を実行してください。")
    logging.critical("="*50)

logger = logging.getLogger(__name__)

# --- ▼▼▼ 設定 (ハードコード) ▼▼▼ ---

# V6.3: PreshareKey を削除

# キー導出用のソルト (これは固定でOK)
SALT = b'q\x8a\x0e\x9b\xf6\x0c\x94\xa8\x8d\x1b\xd3\x99\xe3\x8f\x0b\x1d'

# --- ▲▲▲ 設定ここまで ▲▲▲ ---

_fernet_instance = None

def _get_machine_key() -> str:
    """ (V6.3) PC固有のMACアドレスを取得し、キーとして使用する """
    try:
        # getnode() はMACアドレスを 48ビットの整数として返す
        mac_num = uuid.getnode()
        
        if (mac_num >> 40) % 2:
            # ローカル管理アドレス (プライベートMACなど) の場合は信頼性が低いため警告
            logger.warning("MACアドレスがローカル管理アドレス（ランダムMACなど）の可能性があります。")
            logger.warning("PC再起動やWi-FiのON/OFFで .env が読めなくなる場合があります。")

        # 整数を 12桁の16進数文字列（例: '001a2b3c4d5e'）に変換
        mac_str = format(mac_num, 'x').zfill(12)
        
        if mac_str == '000000000000':
            raise ValueError("有効なMACアドレスを取得できませんでした (00:00:...)。")
            
        logger.info(f"マシン固有キー (MAC) の取得成功: ...{mac_str[-6:]}")
        return mac_str
        
    except Exception as e:
        logger.error(f"マシン固有キー (MAC) の取得に失敗しました: {e}", exc_info=True)
        # 究極のフォールバック (固定文字列)
        return "fallback-static-key-if-mac-fails"


def _get_fernet_instance():
    """ Fernetインスタンスを初期化・取得する """
    global _fernet_instance
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
        
    if _fernet_instance:
        return _fernet_instance

    try:
        # ★ V6.3: PRESHARE_KEY の代わりに MACアドレス を使用
        machine_key_str = _get_machine_key()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=SALT,
            iterations=100000,
        )
        # マシンキー (MAC) から 32バイトのキーを導出
        key_bytes = kdf.derive(machine_key_str.encode('utf-8'))
        # Fernet が要求する base64 エンコードキーに変換
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        
        _fernet_instance = Fernet(fernet_key)
        logger.info("Fernet (暗号化) インスタンスの初期化に成功しました。")
        return _fernet_instance
    except Exception as e:
        logger.error(f"Fernet インスタンスの初期化に失敗: {e}", exc_info=True)
        return None

def encrypt(plain_text: str) -> str:
    """ 文字列を暗号化する """
    if not CRYPTOGRAPHY_AVAILABLE:
        logger.error("cryptography ライブラリがないため暗号化できません。平文で返します。")
        return plain_text 
    
    fernet = _get_fernet_instance()
    if not fernet:
        logger.error("Fernet インスタンスの取得に失敗。平文で返します。")
        return plain_text 

    try:
        encrypted_bytes = fernet.encrypt(plain_text.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"暗号化に失敗: {e}", exc_info=True)
        return plain_text 

def decrypt(encrypted_text: str) -> str:
    """ 文字列を復号する """
    if not CRYPTOGRAPHY_AVAILABLE:
        logger.error("cryptography ライブラリがないため復号できません。")
        return encrypted_text 
        
    fernet = _get_fernet_instance()
    if not fernet:
        logger.error("Fernet インスタンスの取得に失敗。")
        return encrypted_text 

    try:
        # Fernet 暗号は 'gAAAAA...' で始まる
        if not encrypted_text.startswith('gAAAAA'):
            logger.warning("暗号化された文字列ではありません (平文のようです)。そのまま返します。")
            return encrypted_text
            
        decrypted_bytes = fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.warning(f"復号に失敗しました: {e} (PCを移行したか、MACアドレスが変更された可能性があります)")
        return encrypted_text # 復号失敗時 (平文など) はそのまま返す