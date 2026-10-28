def evaluate_user_access(user_role: str, has_payment_history: bool, is_gate_full: bool) -> str:
    """
    ユーザーのアクセス可否および誘導先を判定する
    """
    # 1. tester は常に即課金（テスト用）フローへ
    if user_role == "tester":
        return "redirect_to_stripe"
        
    # 2. supporter は課金履歴があり、残数が切れていても即課金（または優先入場）で通す
    if user_role == "supporter" or has_payment_history:
        return "allow_entry"
        
    # 3. visitor は門番の定員（is_gate_full）に依存する
    if user_role == "visitor":
        if is_gate_full:
            return "blocked_by_gatekeeper"  # 門前払い（どれだけ弾かれたかログに残す）
        else:
            return "allow_entry_free"       # まだ枠が空いていれば無料枠で通す
            
    return "blocked_by_gatekeeper"
