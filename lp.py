# lp.py
import os
import html


def render_lp(status: dict = None, ref: str = "", **kwargs) -> str:
    status = status or {}
    safe_ref = html.escape(ref.strip()) if ref else ""

    line_url = (
        kwargs.get("line_url")
        or os.getenv("LINE_ADD_FRIEND_URL")
        or os.getenv("LINE_FRIEND_URL")
        or "https://line.me/R/"
    )

    is_open = status.get("is_open", True)
    remaining = status.get("remaining", status.get("available_slots", None))
    gate_msg = status.get("message", "")

    if not is_open:
        live_badge_color = "#e11d48"
        live_status_text = gate_msg or "現在満員（留守中）・ファストパス枠のみ案内中"
    else:
        live_badge_color = "#10b981"
        if remaining is not None:
            live_status_text = gate_msg or f"現在入庵可能（本日の無料案内枠 残り {remaining} 名）"
        else:
            live_status_text = gate_msg or "現在入庵可能（通常案内中）"

    live_status_text = html.escape(str(live_status_text))

    ref_banner_html = ""
    if safe_ref:
        ref_banner_html = f"""
        <div class="ref-notice">
            ✨ 特別なお導き（紹介コード: <span>{safe_ref}</span>）経由で入庵中
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI一休さん｜草庵の門を叩く</title>
    <style>
        :root {{
            --bg: #121214;
            --card: #1e1e24;
            --text: #f3f4f6;
            --muted: #9ca3af;
            --accent: #d97706;
            --accent-light: rgba(217, 119, 6, 0.15);
            --line-green: #06c755;
            --border: #2e2e38;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.7;
            padding: 24px 16px 48px;
        }}
        .container {{
            max-width: 500px;
            margin: 0 auto;
        }}
        .ref-notice {{
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid #f59e0b;
            color: #fbbf24;
            font-size: 0.82rem;
            font-weight: 600;
            text-align: center;
            padding: 8px 12px;
            border-radius: 999px;
            margin-bottom: 16px;
        }}
        .ref-notice span {{
            font-family: monospace;
        }}
        .hero {{
            background: var(--card);
            border-radius: 20px;
            padding: 32px 22px;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border);
            text-align: center;
            margin-bottom: 20px;
        }}
        .reel-tag {{
            display: inline-block;
            background: var(--accent-light);
            color: #fbbf24;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 999px;
            margin-bottom: 14px;
            white-space: nowrap;
        }}
        .hero h1 {{
            font-size: 1.42rem;
            font-weight: 800;
            line-height: 1.45;
            margin-bottom: 14px;
            letter-spacing: -0.02em;
            word-break: auto-phrase;
        }}
        .lead {{
            font-size: 0.94rem;
            color: #d1d5db;
            margin-bottom: 22px;
        }}
        .hook-list {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 24px;
            text-align: left;
            font-size: 0.88rem;
            color: #e5e7eb;
        }}
        .hook-list p + p {{
            margin-top: 8px;
        }}
        .cta-btn {{
            display: block;
            width: 100%;
            background: var(--line-green);
            color: #ffffff;
            text-decoration: none;
            font-size: 1.06rem;
            font-weight: 800;
            padding: 16px 20px;
            border-radius: 14px;
            box-shadow: 0 6px 18px rgba(6, 199, 85, 0.28);
            transition: transform 0.15s ease;
        }}
        .cta-btn:active {{
            transform: scale(0.98);
        }}
        .sub-note {{
            margin-top: 10px;
            font-size: 0.78rem;
            color: var(--muted);
        }}
        .referral-hint {{
            margin-top: 20px;
            background: rgba(245, 158, 11, 0.08);
            border: 1px dashed rgba(245, 158, 11, 0.35);
            border-radius: 12px;
            padding: 10px 14px;
            font-size: 0.82rem;
            font-weight: 600;
            color: #fbbf24;
        }}
        .referral-hint span {{
            display: block;
            font-size: 0.74rem;
            font-weight: 400;
            color: var(--muted);
            margin-top: 2px;
        }}
        .live-footer {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 14px;
            font-size: 0.8rem;
            color: var(--muted);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }}
        .live-left {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .live-pill {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: #111827;
            color: #ffffff;
            font-size: 0.7rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 999px;
            letter-spacing: 0.05em;
            flex-shrink: 0;
            border: 1px solid var(--border);
        }}
        .live-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: {live_badge_color};
        }}
        .live-text {{
            font-size: 0.78rem;
            color: var(--muted);
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        {ref_banner_html}

        <section class="hero">
            <div class="reel-tag">🍶 破戒僧・一休宗純の草庵</div>
            <h1>煩悩も理屈も、<br>まずは一休にぶつけてみなされ。</h1>
            <p class="lead">
                説教くさい正解はなし。酒と肉と毒とユーモアで、<br>
                絡まった頭と心をスッとほぐす問答チャット。
            </p>

            <div class="hook-list">
                <p>・愚痴やモヤモヤをそのまま投げ込む</p>
                <p>・あえてボケたり、毒を吐かせて遊ぶ</p>
                <p>・まずは5回分、気軽に草庵を覗いてみる</p>
            </div>

            <a href="{html.escape(line_url)}" class="cta-btn">LINEで一休さんと問答する（無料5回）</a>
            <div class="sub-note">友だち追加後すぐに5回分お試しいただけます</div>

            <div class="referral-hint">
                🎁 気まぐれな一休さんのご縁で、紹介特典が舞い込むことも
                <span>※まずは自分の煩悩をぶつけるのが先じゃ</span>
            </div>
        </section>

        <footer class="live-footer">
            <div class="live-left">
                <span class="live-pill"><span class="live-dot"></span>LIVE</span>
                <span class="live-text">{live_status_text}</span>
            </div>
        </footer>
    </div>
</body>
</html>
"""
