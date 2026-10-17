from datetime import datetime, timezone, timedelta

def get_current_jst_str() -> str:
    """
    データベース（text型）にそのまま保存するための、
    日本時間の「YYYY-MM-DD HH:MM:SS」形式の文字列を返す。
    """
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
