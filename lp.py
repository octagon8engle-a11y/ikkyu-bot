# lp.py
import os
import html


def render_lp(status: dict = None, ref: str = "", **kwargs) -> str:
    status = status or {}
    safe_ref = html.escape(ref.strip()) if ref else ""

    # 環境変数からLINE友だち追加URL・Stripeリンクを取得（未設定時のフォールバック付き）
    line_url = (
        kwargs.get("line_url")
        or os.getenv("LINE_ADD_FRIEND_URL")
        or os.getenv("LINE_FRIEND_URL")
        or "https://line.me/R/"
    )
    stripe_url = (
        kwargs.get("stripe_url")
        or os.getenv("STRIPE_PAYMENT_LINK")
        or os.getenv("STRIPE_URL")
        or "#oshinagaki"
    )

    # ゲート状況（下部のLIVE表示用）
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

    # 紹介リンク経由で来た場合のさりげない表示（詳細は伏せる）
    ref_banner_html = ""
    if safe_ref:
        ref_banner_html = f"""
        <div class="ref-notice">
            ✨ 特別なお導き（紹介コード: <span>{safe_ref}</span>）経由でアクセス中
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI一休さん｜あのチャットがついにあなたも体験できる！</title>
    <style>
        :root {{
            --bg: #faf8f5;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --accent: #b45309;
            --accent-light: #fef3c7;
            --line-green: #06c755;
            --stripe-blue: #635bff;
            --border: #e5e7eb;
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
            line-height: 1.65;
            padding: 20px 16px 48px;
        }}
        .container {{
            max-width: 520px;
            margin: 0 auto;
        }}
        .ref-notice {{
            background: #fffbeb;
            border: 1px solid #fcd34d;
            color: #92400e;
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
        /* ファーストビュー：一番大きく */
        .hero {{
            background: var(--card);
            border-radius: 20px;
            padding: 28px 22px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border);
            text-align: center;
            margin-bottom: 24px;
        }}
        .reel-tag {{
            display: inline-block;
            background: var(--accent-light);
            color: var(--accent);
            font-size: 0.8rem;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 999px;
            margin-bottom: 12px;
        }}
        .hero h1 {{
            font-size: 1.55rem;
            font-weight: 800;
            line-height: 1.35;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
        }}
        .highlight-boxes {{
            display: grid;
            gap: 12px;
            margin-bottom: 22px;
            text-align: left;
        }}
        .highlight-card {{
            border-radius: 14px;
            padding: 16px 18px;
            border: 2px solid transparent;
        }}
        .highlight-free {{
            background: #ecfdf5;
            border-color: #a7f3d0;
        }}
        .highlight-free .badge {{
            display: inline-block;
            background: #059669;
            color: #fff;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            margin-bottom: 4px;
        }}
        .highlight-free .title {{
            font-size: 1.25rem;
            font-weight: 800;
            color: #065f46;
        }}
        .highlight-free .desc {{
            font-size: 0.88rem;
            color: #047857;
            margin-top: 2px;
        }}
        .highlight-stripe {{
            background: #eef2ff;
            border-color: #c7d2fe;
        }}
        .highlight-stripe .badge {{
            display: inline-block;
            background: var(--stripe-blue);
            color: #fff;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            margin-bottom: 4px;
        }}
        .highlight-stripe .title {{
            font-size: 1.15rem;
            font-weight: 800;
            color: #3730a3;
        }}
        .highlight-stripe .desc {{
            font-size: 0.86rem;
            color: #4338ca;
            margin-top: 2px;
        }}
        .cta-btn {{
            display: block;
            width: 100%;
            background: var(--line-green);
            color: #ffffff;
            text-decoration: none;
            font-size: 1.1rem;
            font-weight: 800;
            padding: 16px 20px;
            border-radius: 14px;
            box-shadow: 0 6px 16px rgba(6, 199, 85, 0.28);
            transition: transform 0.15s ease;
        }}
        .cta-btn:active {{
            transform: scale(0.98);
        }}
        /* 特典フック：詳細は伏せてふんわり乗っける */
        .referral-hint {{
            margin-top: 16px;
            background: #fffbeb;
            border: 1px dashed #f59e0b;
            border-radius: 12px;
            padding: 12px 14px;
            font-size: 0.92rem;
            font-weight: 700;
            color: #92400e;
        }}
        .referral-hint span {{
            display: block;
            font-size: 0.78rem;
            font-weight: 500;
            color: #b45309;
            margin-top: 2px;
        }}
        /* お品書き：そこそこの大きさ */
        .menu-section {{
            background: var(--card);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
        }}
        .menu-section h2 {{
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .menu-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 11px 0;
            border-bottom: 1px dashed #f3f4f6;
            font-size: 0.92rem;
        }}
        .menu-item:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}
        .menu-name {{
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .menu-tag {{
            font-size: 0.7rem;
            font-weight: 700;
            background: var(--accent-light);
            color: var(--accent);
            padding: 1px 6px;
            border-radius: 4px;
        }}
        .menu-sub {{
            font-size: 0.8rem;
            color: var(--muted);
            margin-top: 2px;
        }}
        .menu-price {{
            font-weight: 800;
            font-size: 1.02rem;
            color: var(--accent);
            white-space: nowrap;
            margin-left: 12px;
            text-align: right;
        }}
        .menu-price small {{
            display: block;
            font-size: 0.72rem;
            font-weight: 500;
            color: var(--muted);
        }}
        .stripe-note {{
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid #f3f4f6;
            font-size: 0.78rem;
            color: var(--muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .stripe-link {{
            font-size: 0.82rem;
            color: var(--stripe-blue);
            font-weight: 700;
            text-decoration: none;
        }}
        /* USJ方式LIVE：下の方に控えめに */
        .live-footer {{
            background: #f3f4f6;
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
        }}
        .live-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: {live_badge_color};
        }}
        .live-text {{
            font-size: 0.78rem;
            color: #4b5563;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        {ref_banner_html}

        <!-- メイン看板（一番大きく） -->
        <section class="hero">
            <div class="reel-tag">📱 インスタのリールで話題のAI一休さん</div>
            <h1>あのチャットが、<br>ついにあなたも体験できる！</h1>

            <div class="highlight-boxes">
                <div class="highlight-card highlight-free">
                    <span class="badge">まずは気軽に</span>
                    <div class="title">初回5回まで完全無料でお試し！</div>
                    <div class="desc">LINEを追加するだけですぐに問答スタート。自動課金は一切ありません。</div>
                </div>

                <div class="highlight-card highlight-stripe">
                    <span class="badge">世界基準の決済システム</span>
                    <div class="title">追加の問答も Stripe 決済で安心・安全</div>
                    <div class="desc">5回550円〜の都度払い。カード情報がボット側に残らない安全決済です。</div>
                </div>
            </div>

            <a href="{html.escape(line_url)}" class="cta-btn">LINEで今すぐ無料お試し（5回分）</a>

            <!-- 特典の匂わせ（詳細は書かない） -->
            <div class="referral-hint">
                🎁 友達にLINEで紹介すると、いいこと（特典）あるかも…？
                <span>※気まぐれな一休さんのご縁次第です</span>
            </div>
        </section>

        <!-- お品書き（そこそこの大きさ・550円 / 990円を明記） -->
        <section class="menu-section" id="oshinagaki">
            <h2>🍶 お品書き（料金案内）</h2>

            <div class="menu-item">
                <div>
                    <div class="menu-name">初回お試し問答（5回分）</div>
                    <div class="menu-sub">LINE登録後すぐに使えます</div>
                </div>
                <div class="menu-price">
                    0円
                    <small>完全無料</small>
                </div>
            </div>

            <div class="menu-item">
                <div>
                    <div class="menu-name">追加お布施・竹（5回分）</div>
                    <div class="menu-sub">1回あたり110円・都度チャージ</div>
                </div>
                <div class="menu-price">
                    550円
                    <small>税込・都度払い</small>
                </div>
            </div>

            <div class="menu-item">
                <div>
                    <div class="menu-name">
                        追加お布施・松（10回分）
                        <span class="menu-tag">お得</span>
                    </div>
                    <div class="menu-sub">1回あたり99円・たっぷり問答したい方に</div>
                </div>
                <div class="menu-price">
                    990円
                    <small>税込・都度払い</small>
                </div>
            </div>

            <div class="stripe-note">
                <span>※自動更新（サブスク）なし</span>
                <a href="{html.escape(stripe_url)}" class="stripe-link">Stripe決済ページを見る →</a>
            </div>
        </section>

        <!-- USJ方式：下の方にLIVEとして控えめに配置 -->
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
