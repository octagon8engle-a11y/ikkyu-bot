from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DAILY_FREE_CAPACITY = 5  # 1日の一般スタンバイ基本枠（お好みで調整可能）

def calculate_gate_status(supabase_client) -> dict:
    """
    本日のチャット履歴や課金履歴を元に、USJゲートの混雑状況と無料枠の残数を自動計算する
    """
    today_prefix = datetime.now(JST).strftime("%Y-%m-%d")
    
    try:
        # 1. 本日チャットしたユニークユーザーを取得
        res_chats = supabase_client.table("chat_logs_v2_1") \
            .select("user_id").gte("created_at", f"{today_prefix} 00:00:00").execute()
        today_users = list({row["user_id"] for row in res_chats.data if row.get("user_id")})

        # 2. 課金履歴のあるユーザー（ファストパス保持者）を取得
        res_paid = supabase_client.table("stripe_transactions_v2_1") \
            .select("user_id").gt("amount", 0).execute()
        paid_users = {row["user_id"] for row in res_paid.data if row.get("user_id")}

        fastpass_today = sum(1 for u in today_users if u in paid_users)
        free_today = sum(1 for u in today_users if u not in paid_users)

        # ファストパス利用者が増えると、一般の無料枠も少しだけおまけで開放されるUSJ式ロジック
        total_free_cap = DAILY_FREE_CAPACITY + (fastpass_today // 2)
        free_remaining = max(0, total_free_cap - free_today)

        return {
            "fastpass_today": fastpass_today,
            "free_today": free_today,
            "free_remaining": free_remaining,
            "is_gate_full": free_remaining <= 0
        }
    except Exception as e:
        print(f"Gate status calculation error: {e}")
        # エラー時は安全のため枠を0（満杯＝留守札）として返す
        return {
            "fastpass_today": 0,
            "free_today": 0,
            "free_remaining": 0,
            "is_gate_full": True
        }

def evaluate_user_access(has_payment_history: bool, has_referrer: bool, is_gate_full: bool) -> str:
    """
    ユーザーのアクセス可否および誘導先を自動判定する
    - 課金履歴あり or 紹介(referrer)持ち → 優先入場（allow_entry）
    - 課金なし・紹介なし → ゲートの空き状況（is_gate_full）で自動判定
    """
    # 1. 課金済み、または紹介者（referrer）経由の人は無条件で優先入場
    if has_payment_history or has_referrer:
        return "allow_entry"
        
    # 2. 一般の通りすがり（ビジター）の場合、ゲートの満杯状況に依存する
    if is_gate_full:
        return "blocked_by_gatekeeper"  # 門前払い（留守札表示）
    else:
        return "allow_entry_free"       # まだ無料枠が空いているので通す
