# lp.py
import os

STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5", "#")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10", "#")
LINE_BOT_URL = os.getenv("LINE_BOT_URL", "https://line.me/R/ti/p/@YOUR_LINE_BOT_ID")

def render_lp(gate_status: dict, ref: str = "") -> str:
    """
    USJ式ゲートステータスを受け取り、破戒僧の世界観を反映したLPのHTMLを動的に生成する
    """
    fastpass_count = gate_status.get("fastpass_today", 0)
    free_passed_count = gate_status.get("free_today", 0)
    free_remaining = gate_status.get("free_remaining", 0)
    is_gate_full = gate_status.get("is_gate_full", True)

    # 残り枠に応じた一般スタンバイのステータス文言・色の切り替え（破戒僧フレーズ連動）
    if not is_gate_full and free_remaining > 0:
        free_status_text = f"受付中（本日残り {free_remaining} 枠）"
        free_status_color = "#f59e0b" # 警告オレンジ
    else:
        free_status_text = "🚪 本日は町へ酒と肉の修行につき留守（門前払い）"
        free_status_color = "#ef4444" # 終了レッド

    # 紹介者パラメータ(ref)の処理
    ref_param = f"&text=ref:{ref}" if ref else ""
    line_url = f"{LINE_BOT_URL}{ref_param}"

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI一休さん - 現代の草庵</title>
    <style>
        :root {{
            --bg-color: #0f141c;
            --card-bg: #1a2230;
            --accent-gold: #d4af37;
            --fastpass-glow: #ffd700;
            --text-main: #f0f4f8;
            --text-sub: #94a3b8;
            --border-color: #2a364d;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .container {{
            width: 100%;
            max-width: 480px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 28px 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            text-align: center;
        }}
        h1 {{
            font-size: 1.5rem;
            margin-bottom: 8px;
            color: var(--text-main);
            letter-spacing: 0.05em;
        }}
        .subtitle {{
            color: var(--text-sub);
            font-size: 0.9rem;
            margin-bottom: 20px;
        }}
        
        /* USJ風 リアルタイム・ゲート表示ボード */
        .gate-board {{
            background: #0a0e14;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: left;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.6);
        }}
        .gate-header {{
            font-size: 0.8rem;
            color: var(--text-sub);
            letter-spacing: 0.08em;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 8px;
        }}
        .live-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            margin-right: 6px;
            box-shadow: 0 0 8px #10b981;
        }}
        .lane-card {{
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }}
        .lane-card:last-child {{
            margin-bottom: 0;
        }}
        /* ファストパスレーン（VIP仕様） */
        .lane-fastpass {{
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.18), rgba(212, 175, 55, 0.05));
            border: 1px solid rgba(212, 175, 55, 0.6);
        }}
        .lane-title-fp {{
            color: var(--fastpass-glow);
            font-weight: bold;
            font-size: 0.92rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .badge-instant {{
            background: var(--accent-gold);
            color: #000;
            font-size: 0.7rem;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        /* 一般スタンバイレーン */
        .lane-general {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid #2a364d;
        }}
        .lane-title-gen {{
            color: #cbd5e1;
            font-weight: bold;
            font-size: 0.88rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .lane-stats {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            color: var(--text-sub);
            margin-top: 6px;
        }}
        .lane-stats strong {{
            color: var(--text-main);
            font-size: 0.9rem;
        }}

        /* セクション・価格ボックス */
        .section-box {{
            background: rgba(15, 20, 28, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            text-align: left;
        }}
        .section-box h3 {{
            color: var(--accent-gold);
            font-size: 0.92rem;
            margin-bottom: 8px;
        }}
        .price-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }}
        .price-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px;
            text-align: center;
        }}
        .price-card .num {{
            font-size: 1.1rem;
            font-weight: bold;
            color: var(--accent-gold);
        }}
        .price-card .label {{
            font-size: 0.72rem;
            color: var(--text-sub);
        }}
        .btn-line {{
            display: block;
            width: 100%;
            background-color: #06c755;
            color: white;
            text-align: center;
            padding: 14px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1.02rem;
            text-decoration: none;
            box-shadow: 0 4px 12px rgba(6, 199, 85, 0.3);
            margin-bottom: 14px;
        }}
        .btn-fp {{
            display: block;
            width: 100%;
            background: linear-gradient(135deg, #d4af37, #b5952f);
            color: #0f141c;
            text-align: center;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.9rem;
            text-decoration: none;
            margin-top: 8px;
        }}
        .stripe-badge {{
            font-size: 0.75rem;
            color: var(--text-sub);
            margin-top: 10px;
        }}
        .stripe-badge span {{
            color: #635bff;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div style="color: var(--accent-gold); font-size: 0.8rem; margin-bottom: 6px;">🍶 現代の草庵・問答所</div>
        <h1>AI一休の草庵</h1>
        <p class="subtitle">煩悩まみれの世迷い言、トンチの和尚がズバッと断ち切るわい。</p>
        
        <!-- USJ式 リアルタイム・ゲート表示ボード -->
        <div class="gate-board">
            <div class="gate-header">
                <span><span class="live-dot"></span>本日の草庵 受付状況</span>
                <span>LIVE</span>
            </div>
            
            <!-- ファストパスレーン -->
            <div class="lane-card lane-fastpass">
                <div class="lane-title-fp">
                    <span>⚡ ファストパス（お布施優先）</span>
                    <span class="badge-instant">待ち時間 0分</span>
                </div>
                <div class="lane-stats">
                    <span>状態：<strong>裏口から即時案内中</strong></span>
                    <span>本日通過：<strong>{fastpass_count} 名</strong></span>
                </div>
            </div>

            <!-- 一般スタンバイレーン -->
            <div class="lane-card lane-general">
                <div class="lane-title-gen">
                    <span>🐢 一般スタンバイ（無料お試し）</span>
                </div>
                <div class="lane-stats">
                    <span style="color: {free_status_color}; font-weight: bold; font-size: 0.78rem;">{free_status_text}</span>
                    <span>本日通過：<strong>{free_passed_count} 名</strong></span>
                </div>
            </div>
        </div>

        <a href="{line_url}" class="btn-line">一般スタンバイで門を叩く</a>

        <!-- ファストパス（お布施チケット） -->
        <div class="section-box" style="border-left: 4px solid var(--accent-gold);">
            <h3>⚡ ファストパス（お布施・優先入場）</h3>
            <p style="font-size: 0.8rem; color: var(--text-sub); margin-bottom: 10px;">
                留守札を無視して、酒代（お布施）を積んで酔っ払った和尚を裏口から叩き起こす！
            </p>
            <a href="{STRIPE_LINK_5}" class="btn-fp">5回券（550円）で優先入場する</a>
            <a href="{STRIPE_LINK_10}" class="btn-fp">10回券（990円）で優先入場する</a>
        </div>
        
        <div class="stripe-badge">
            🔒 安全な <span>Stripe</span> 決済（クレカ / Apple Pay / Google Pay）
        </div>
    </div>
</body>
</html>"""
    return html_content
