#!/usr/bin/env python3
"""
Rebuilds the pokemon-model.astro page from latest results_v3.json
and pushes to GitHub so Vercel redeploys automatically.
"""
import json, subprocess
from datetime import datetime
from pathlib import Path

print(f"[{datetime.now().isoformat()}] Rebuilding pokemon model page...")

# Run the model to get fresh results
result = subprocess.run(
    ['python3', '/opt/orchid/apps/pokemon-model/model_v3.py'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"Model failed: {result.stderr}")
    exit(1)
print("Model complete. Generating page...")

# Load fresh results
with open('/opt/orchid/apps/pokemon-model/results_v3.json') as f:
    data = json.load(f)

top25     = data['top25']
generated = data['generated'][:10]
buys      = [r for r in top25 if r['signal'] == 'BUY']
watches   = [r for r in top25 if r['signal'] == 'WATCH']
holds     = [r for r in top25 if r['signal'] == 'HOLD']
db_sigs   = data.get('db_signals', {})
total     = data['total_analyzed']

SIG_COLOR  = {'BUY':'#4caf50','WATCH':'#c4972a','HOLD':'#5a5752','AVOID':'#c45a5a'}
TYPE_LABEL = {'vintage_single':'🏛 Vintage','modern_single':'✨ Modern','sealed':'📦 Sealed'}
TYPE_COLOR = {'vintage_single':'#c4972a','modern_single':'#7eb8c4','sealed':'#9b8a6e'}

def fmt_price(p):
    if not p: return '—'
    return f"${p:,.0f}" if p >= 100 else f"${p:.2f}"

def score_bars(scores, ctype):
    color = TYPE_COLOR.get(ctype,'#7eb8c4')
    return ''.join(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:.54rem;color:#5a5752;width:100px;flex-shrink:0">{k.replace("_"," ").title()}</div>'
        f'<div style="flex:1;height:2px;background:#121210;border-radius:1px;overflow:hidden">'
        f'<div style="height:100%;width:{v*100:.0f}%;background:{color}"></div></div>'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:.54rem;color:#5a5752;width:28px;text-align:right">{v:.2f}</div></div>'
        for k, v in scores.items()
    )

def card_html(r):
    sc     = r['signal']
    sig_c  = SIG_COLOR.get(sc,'#5a5752')
    type_c = TYPE_COLOR.get(r['type'],'#7eb8c4')
    type_l = TYPE_LABEL.get(r['type'],r['type'])
    trend  = r.get('cm_trend',0)
    trend_s = f"{trend:+.0f}%" if trend else '—'
    trend_c = '#4caf50' if trend>5 else '#c45a5a' if trend<-5 else '#5a5752'

    if r['type']=='sealed':
        price_line = f'<div style="font-family:JetBrains Mono,monospace;font-size:.6rem;color:#5a5752;margin-top:4px">MSRP ${r.get("msrp",65)} · Now {fmt_price(r["tcg_market"])} (+{r.get("premium_pct",0):.0f}%)</div>'
        trend_line = ''
    else:
        price_line = f'<div style="font-family:JetBrains Mono,monospace;font-size:.6rem;color:#5a5752;margin-top:4px">Market {fmt_price(r["tcg_market"])} · All-in ~{fmt_price(r["all_in_cost"])}</div>'
        trend_line = f'<div style="font-family:JetBrains Mono,monospace;font-size:.6rem;color:#5a5752;margin-top:2px">CM 7d: <span style="color:{trend_c}">{trend_s}</span></div>'

    return f'''
    <div style="background:#0d0d0b;border:1px solid rgba(255,255,255,.06);border-left:3px solid {sig_c};padding:20px 22px;margin-bottom:2px;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;">
        <div>
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
            <span style="font-family:JetBrains Mono,monospace;font-size:.55rem;color:#5a5752">#{r['rank']}</span>
            <span style="font-family:JetBrains Mono,monospace;font-size:.55rem;color:{type_c};border:1px solid {type_c}33;padding:2px 7px">{type_l}</span>
          </div>
          <div style="font-family:DM Serif Display,Georgia,serif;font-size:1.15rem;color:#e8e6e1">{r['name']}</div>
          <div style="font-family:JetBrains Mono,monospace;font-size:.6rem;color:#5a5752;margin-top:2px">{r['set']}</div>
          {price_line}{trend_line}
        </div>
        <div style="text-align:right;flex-shrink:0;margin-left:16px">
          <div style="font-family:JetBrains Mono,monospace;font-size:.58rem;color:{sig_c};border:1px solid {sig_c}44;padding:3px 10px;letter-spacing:.12em;margin-bottom:6px">{sc}</div>
          <div style="font-family:JetBrains Mono,monospace;font-size:1.2rem;color:{sig_c}">{r['composite_score']:.3f}</div>
        </div>
      </div>
      <div style="margin-bottom:8px">{score_bars(r['scores'],r['type'])}</div>
      <div style="font-family:JetBrains Mono,monospace;font-size:.6rem;color:#5a5752;font-style:italic">{r['notes'][:100]}</div>
    </div>'''

def section_label(color, text):
    return f'''
<div style="font-family:JetBrains Mono,monospace;font-size:.62rem;color:{color};letter-spacing:.16em;text-transform:uppercase;display:flex;align-items:center;gap:12px;margin-bottom:20px;margin-top:52px">
  <span style="width:20px;height:1px;background:{color};display:inline-block"></span>{text}
  <span style="flex:1;height:1px;background:{color}33;display:inline-block"></span>
</div>'''

page = f'''---
import Base from '../../layouts/Base.astro';
---
<Base title="Vessel Pokémon Model" description="Top 25 Pokémon acquisition targets — vintage, modern, and sealed. Powered by a live database of {total:,} cards across 172 sets. Updated daily.">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
:root{{
  --bg:#090908;--bg-2:#0d0d0b;--bg-3:#121210;
  --amber:#c4972a;--amber-border:rgba(196,151,42,.15);--amber-dim:rgba(196,151,42,.08);
  --vessel:#7eb8c4;--vessel-border:rgba(126,184,196,.12);
  --text:#e8e6e1;--text-2:#a09c94;--text-3:#5a5752;
  --green:#4caf50;--red:#c45a5a;
  --serif:'DM Serif Display',Georgia,serif;
  --sans:'DM Sans',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,monospace;
  --gutter:clamp(24px,5vw,80px);--max:1100px;--nav-h:68px;
}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-weight:300;line-height:1.7;-webkit-font-smoothing:antialiased;overflow-x:hidden;}}
nav{{position:fixed;top:0;left:0;right:0;z-index:200;height:var(--nav-h);display:flex;align-items:center;justify-content:space-between;padding:0 var(--gutter);border-bottom:1px solid transparent;transition:all .4s;}}
nav.scrolled{{border-color:var(--amber-border);background:rgba(9,9,8,.93);backdrop-filter:blur(14px);}}
.nav-logo{{font-family:var(--serif);font-size:1.05rem;color:var(--text);text-decoration:none;}}
.nav-logo span{{color:var(--amber);}}
.hero{{min-height:100vh;display:flex;flex-direction:column;justify-content:flex-end;padding:0 var(--gutter) 80px;position:relative;overflow:hidden;}}
.hero-bg{{position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 20% 70%,rgba(196,151,42,.04),transparent 60%);}}
.hero-label{{position:relative;z-index:1;font-family:var(--mono);font-size:.62rem;color:var(--amber);letter-spacing:.16em;text-transform:uppercase;margin-bottom:24px;display:flex;align-items:center;gap:14px;animation:rise .7s .2s both;}}
.hero-label::before{{content:'';width:28px;height:1px;background:var(--amber);}}
.hero h1{{position:relative;z-index:1;font-family:var(--serif);font-size:clamp(2.8rem,5.5vw,5.5rem);font-weight:400;line-height:1.05;letter-spacing:-.025em;animation:rise .9s .3s both;}}
.hero h1 em{{font-style:italic;color:var(--amber);}}
.hero-sub{{position:relative;z-index:1;margin-top:20px;max-width:540px;font-size:1rem;color:var(--text-2);line-height:1.75;animation:rise .9s .45s both;}}
.stats{{position:relative;z-index:1;margin-top:44px;display:flex;gap:2px;flex-wrap:wrap;animation:rise .9s .6s both;}}
.stat{{background:var(--bg-2);border:1px solid var(--amber-border);padding:16px 24px;}}
.stat-num{{font-family:var(--mono);font-size:1.4rem;color:var(--amber);letter-spacing:-.02em;line-height:1;}}
.stat-num.up{{color:var(--green);}} .stat-num.watch{{color:var(--amber);}}
.stat-label{{font-family:var(--mono);font-size:.54rem;color:var(--text-3);letter-spacing:.1em;text-transform:uppercase;margin-top:4px;}}
.content{{max-width:calc(var(--max) + var(--gutter)*2);margin:0 auto;padding:60px var(--gutter) 100px;}}
.advisor-cta{{background:var(--amber-dim);border:1px solid var(--amber-border);border-left:3px solid var(--amber);padding:24px 32px;margin-bottom:48px;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px;}}
.li{{display:flex;align-items:center;gap:7px;font-family:var(--mono);font-size:.6rem;color:var(--text-3);letter-spacing:.07em;}}
.ld{{width:8px;height:8px;border-radius:50%;}}
.method{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;margin-top:52px;}}
.mc{{background:var(--bg-2);border:1px solid var(--amber-border);padding:24px 20px;}}
.mc-label{{font-family:var(--mono);font-size:.56rem;color:var(--amber);letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px;}}
.mc-desc{{font-family:var(--mono);font-size:.63rem;color:var(--text-3);line-height:1.65;}}
.site-footer{{border-top:1px solid var(--amber-border);padding:40px var(--gutter);display:flex;align-items:center;justify-content:space-between;max-width:calc(var(--max) + var(--gutter)*2);margin:0 auto;}}
@keyframes rise{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
@media(max-width:800px){{.stats{{flex-direction:column;}}.method{{grid-template-columns:1fr;}}}}
</style>

<nav id="nav">
  <a class="nav-logo" href="/">matter<span>unknown</span></a>
  <a href="/projects" style="font-family:var(--mono);font-size:.65rem;color:var(--text-3);letter-spacing:.1em;text-transform:uppercase;text-decoration:none;">← Projects</a>
</nav>

<div class="hero">
  <div class="hero-bg"></div>
  <div class="hero-label">Vessel / Pokémon Acquisition Model v3</div>
  <h1>{total:,} cards.<br><em>25 targets.</em></h1>
  <p class="hero-sub">Every Pokémon set ever printed — 172 sets, {total:,} cards scored. Vintage singles, modern singles, sealed product. Top 25 across buy signals, watch list, and holds — updated daily from live price data.</p>
  <div class="stats">
    <div class="stat"><div class="stat-num up">{len(buys)}</div><div class="stat-label">Buy signals</div></div>
    <div class="stat"><div class="stat-num watch">{len(watches)}</div><div class="stat-label">Watch list</div></div>
    <div class="stat"><div class="stat-num">{len(holds)}</div><div class="stat-label">Hold</div></div>
    <div class="stat"><div class="stat-num">{db_sigs.get("BUY",0)}</div><div class="stat-label">Total buys in DB</div></div>
    <div class="stat"><div class="stat-num">{total:,}</div><div class="stat-label">Cards scored</div></div>
    <div class="stat"><div class="stat-num">{generated}</div><div class="stat-label">Updated</div></div>
  </div>
</div>

<div class="content">

  <div class="advisor-cta">
    <div>
      <div style="font-family:var(--mono);font-size:.58rem;color:var(--amber);letter-spacing:.14em;text-transform:uppercase;margin-bottom:6px">Personalized recommendations</div>
      <div style="font-family:DM Serif Display,Georgia,serif;font-size:1.15rem;color:var(--text);margin-bottom:4px">Own Pokémon cards? Get a custom buy list.</div>
      <div style="font-family:var(--mono);font-size:.65rem;color:var(--text-2)">Enter your collection — Vessel maps it against all {total:,} cards and recommends what to buy next.</div>
    </div>
    <a href="/projects/pokemon-advisor" style="flex-shrink:0;background:var(--amber-dim);border:1px solid var(--amber-border);padding:12px 24px;font-family:var(--mono);font-size:.65rem;color:var(--amber);letter-spacing:.1em;text-transform:uppercase;text-decoration:none;white-space:nowrap">Try the advisor →</a>
  </div>

  <div class="legend">
    <div class="li"><div class="ld" style="background:#c4972a"></div>🏛 Vintage</div>
    <div class="li"><div class="ld" style="background:#7eb8c4"></div>✨ Modern</div>
    <div class="li"><div class="ld" style="background:#9b8a6e"></div>📦 Sealed</div>
    <div class="li"><div class="ld" style="background:#4caf50"></div>BUY — strong signal, act now</div>
    <div class="li"><div class="ld" style="background:#c4972a"></div>WATCH — monitor, wait for better entry</div>
    <div class="li"><div class="ld" style="background:#5a5752"></div>HOLD — own it, don't chase it</div>
  </div>
'''

for signal, items, label, color in [
    ('BUY',   buys,   f'Buy signals — {len(buys)} cards',   '#4caf50'),
    ('WATCH', watches,f'Watch list — {len(watches)} cards', '#c4972a'),
    ('HOLD',  holds,  f'Hold — {len(holds)} cards',         '#5a5752'),
]:
    if items:
        page += section_label(color, label)
        for r in items:
            page += card_html(r)

page += f'''
  <div class="method">
    <div class="mc">
      <div class="mc-label">Database — {total:,} cards</div>
      <div class="mc-desc">Every Pokémon set across 172 releases. Prices from TCGplayer live market and Cardmarket 7-day averages. Rebuilt nightly at 2 AM UTC with fresh data.</div>
    </div>
    <div class="mc">
      <div class="mc-label">Scoring</div>
      <div class="mc-desc">Rarity tier (30%), era momentum (20%), price signal (25%), CM 7d trend (15%), chase Pokémon demand bonus (10%). BUY ≥ 0.72 · WATCH ≥ 0.58 · HOLD ≥ 0.42.</div>
    </div>
    <div class="mc">
      <div class="mc-label">Top 25 — balanced</div>
      <div class="mc-desc">~10 BUY, ~10 WATCH, ~5 HOLD. The watch list matters as much as the buy list — these are the cards to monitor for better entry points and emerging momentum.</div>
    </div>
  </div>

</div>

<div class="site-footer">
  <div style="font-family:DM Serif Display,Georgia,serif;font-size:.95rem;color:var(--text-3)">matter<span style="color:var(--amber)">unknown</span></div>
  <div style="font-family:var(--mono);font-size:.56rem;color:var(--text-3);letter-spacing:.07em">{total:,} cards · 172 sets · Updated daily · TCGplayer · Cardmarket</div>
</div>
<script is:inline>
window.addEventListener('scroll',()=>{{ document.getElementById('nav').classList.toggle('scrolled',scrollY>16); }});
</script>
</Base>'''

out = Path('/opt/orchid/apps/matterunknown/src/pages/projects/pokemon-model.astro')
out.write_text(page)
print(f"Page written — {total:,} cards, {len(page)//1024}KB")
