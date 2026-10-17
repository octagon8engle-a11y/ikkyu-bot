from datetime import datetime, timezone, timedelta

def get_current_jst_iso() -> str:
    """
    日本時間の現在時刻をISOフォーマット（タイムゾーン付き）で取得する。
    例: '2026-10-17T22:49:00+09:00'
    """
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).isoformat()
