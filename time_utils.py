from datetime import datetime, timezone, timedelta

def get_current_jst_iso() -> str:
    """日本時間の現在時刻をISOフォーマットで取得する"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).isoformat()
