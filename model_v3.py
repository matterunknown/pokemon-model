#!/usr/bin/env python3
"""
Vessel Pokemon Acquisition Model v3
Queries the full 12,000+ card database instead of a hardcoded list.
Outputs top 25 ranked by composite score across vintage, modern, and sealed.
"""

import json
import sqlite3
import time
import requests
from datetime import datetime
from pathlib import Path

DB_PATH    = '/opt/orchid/apps/pokemon-model/db/cards.db'
RESULTS_V3 = '/opt/orchid/apps/pokemon-model/results_v3.json'

# Sealed product — manually curated since it's not in the TCG card API
SEALED = [
    {"name":"Evolving Skies ETB",         "set":"Evolving Skies",        "current_price":2600, "msrp":65, "chase_strength":1.00, "reprint_risk":0.05, "era":"swsh", "notes":"Gold standard. Ship has sailed on entry."},
    {"name":"Ascended Heroes ETB",        "set":"Ascended Heroes",        "current_price":108,  "msrp":65, "chase_strength":0.95, "reprint_risk":0.45, "era":"sv",   "notes":"Prismatic Evolutions setup. Cases cheap now."},
    {"name":"Destined Rivals ETB",        "set":"Destined Rivals",        "current_price":146,  "msrp":65, "chase_strength":0.85, "reprint_risk":0.30, "era":"sv",   "notes":"Team Rocket nostalgia. Undervalued."},
    {"name":"Prismatic Evolutions ETB",   "set":"Prismatic Evolutions",   "current_price":190,  "msrp":65, "chase_strength":0.95, "reprint_risk":0.55, "era":"sv",   "notes":"Reprinted heavily. Floor likely found."},
    {"name":"Crown Zenith ETB",           "set":"Crown Zenith",           "current_price":230,  "msrp":65, "chase_strength":0.80, "reprint_risk":0.10, "era":"swsh", "notes":"SWSH rotation locks in scarcity."},
    {"name":"Celebrations ETB",           "set":"Celebrations",           "current_price":95,   "msrp":40, "chase_strength":0.75, "reprint_risk":0.05, "era":"swsh", "notes":"25th anniversary. Limited print. Steady appreciation."},
    {"name":"Astral Radiance ETB",        "set":"Astral Radiance",        "current_price":70,   "msrp":45, "chase_strength":0.70, "reprint_risk":0.15, "era":"swsh", "notes":"Rotated SWSH. Supply drying up."},
    {"name":"Brilliant Stars ETB",        "set":"Brilliant Stars",        "current_price":65,   "msrp":45, "chase_strength":0.72, "reprint_risk":0.20, "era":"swsh", "notes":"Charizard VSTAR set. Rotated."},
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def score_sealed(s):
    """Score sealed product."""
    msrp    = s['msrp']
    current = s['current_price']
    chase   = s['chase_strength']
    reprint = s['reprint_risk']
    
    prem = current / msrp
    entry = (1.0 if prem < 1.2 else 0.8 if prem < 1.5 else
             0.6 if prem < 2.0 else 0.3 if prem < 4.0 else 0.1)
    
    reprint_score = 1.0 - reprint
    hold = min(chase * reprint_score, 1.0)
    
    # Era momentum
    era_mom = {'swsh': 0.78, 'sv': 0.72, 'sm': 0.55}.get(s['era'], 0.50)
    
    composite = (entry*0.25 + chase*0.20 + reprint_score*0.20 +
                 era_mom*0.20 + hold*0.15)
    
    signal = ('BUY'   if composite >= 0.72 else
              'WATCH' if composite >= 0.58 else
              'HOLD'  if composite >= 0.42 else 'AVOID')
    
    return {
        'rank': 0,
        'name': s['name'],
        'set': s['set'],
        'type': 'sealed',
        'signal': signal,
        'composite_score': round(composite, 3),
        'tcg_market': current,
        'all_in_cost': current,
        'cm_trend': 0,
        'psa9_pop': 0,
        'psa10_pop': 0,
        'psa10_est': None,
        'msrp': msrp,
        'premium_pct': round((prem - 1) * 100, 1),
        'notes': s['notes'],
        'image': None,
        'scores': {
            'entry': round(entry, 2),
            'chase_strength': round(chase, 2),
            'reprint_safety': round(reprint_score, 2),
            'era_momentum': round(era_mom, 2),
            'hold_thesis': round(hold, 2),
        }
    }

def run():
    print(f"\n{'='*65}")
    print(f"Vessel Pokemon Model v3 — DB-powered")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*65}\n")

    conn = get_db()
    c    = conn.cursor()

    # ── Pull top cards from DB ────────────────────────────────
    # Get top 60 by score — we'll pick the best 25 after adding sealed
    c.execute('''
        SELECT id, name, set_name, era,
               rarity, tcg_market, tcg_low, cm_avg7, cm_avg30, cm_trend,
               score, signal, release_year,
               score_rarity, score_era, score_price, score_momentum, score_chase,
               image_small as image
        FROM cards
        WHERE (tcg_market > 0 OR cm_avg7 > 0)
          AND signal IN ('BUY', 'WATCH', 'HOLD')
          AND score >= 0.50
        ORDER BY score DESC
        LIMIT 60
    ''')
    db_cards = [dict(r) for r in c.fetchall()]
    conn.close()

    print(f"DB cards pulled: {len(db_cards)}")

    # ── Determine type: vintage vs modern ────────────────────
    VINTAGE_ERAS = {'wizards', 'nintendo', 'dp'}
    MODERN_ERAS  = {'bw', 'xy', 'sm', 'swsh', 'sv'}

    results = []
    for card in db_cards:
        era   = card.get('era', 'unknown')
        ctype = ('vintage_single' if era in VINTAGE_ERAS else
                 'modern_single'  if era in MODERN_ERAS  else 'modern_single')

        # Estimate PSA 9 pop from market data (proxy)
        market = card['tcg_market'] or card['cm_avg7'] or 0
        psa9_pop_est = max(1, int(5000 / max(market, 1))) if market > 0 else 0

        # All-in cost estimate for vintage
        all_in = round((card['tcg_low'] or market) * 0.12 + 50, 2) if ctype == 'vintage_single' else market

        results.append({
            'rank': 0,
            'name': card['name'],
            'set': card['set_name'],
            'type': ctype,
            'signal': card['signal'],
            'composite_score': round(card['score'], 3),
            'tcg_market': round(market, 2),
            'all_in_cost': round(all_in, 2),
            'cm_trend': round(card['cm_trend'] or 0, 1),
            'psa9_pop': psa9_pop_est,
            'psa10_pop': 0,
            'psa10_est': None,
            'msrp': None,
            'premium_pct': None,
            'notes': f"Score: {card['score']:.3f} | Era: {era} | Rarity: {card.get('rarity','')}",
            'image': card.get('image'),
            'scores': {
                'rarity':   round(card.get('score_rarity', 0), 2),
                'era':      round(card.get('score_era', 0), 2),
                'price':    round(card.get('score_price', 0), 2),
                'momentum': round(card.get('score_momentum', 0), 2),
                'chase':    round(card.get('score_chase', 0), 2),
            }
        })

    # ── Add sealed product ────────────────────────────────────
    for s in SEALED:
        results.append(score_sealed(s))

    # ── Sort and rank top 25 ──────────────────────────────────
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    top25 = results[:25]
    for i, r in enumerate(top25):
        r['rank'] = i + 1

    # ── Print ─────────────────────────────────────────────────
    SIG = {'BUY':'🟢','WATCH':'🟡','HOLD':'⚪','AVOID':'🔴'}
    TYPE = {'vintage_single':'🏛 ','modern_single':'✨ ','sealed':'📦 '}
    print(f"\n{'='*65}")
    print(f"TOP 25 — DB-powered acquisition list")
    print(f"{'='*65}")
    for r in top25:
        price = f"${r['tcg_market']:,.0f}" if r['tcg_market'] else "N/A"
        trend = f"{r['cm_trend']:+.0f}%" if r['cm_trend'] else "  —  "
        print(f"  #{r['rank']:2} {SIG[r['signal']]}{r['signal']:<6} {r['composite_score']:.3f} "
              f"{TYPE[r['type']]}{r['name']:30} {r['set']:22} {price:>8} {trend}")

    buys = [r for r in top25 if r['signal'] == 'BUY']
    print(f"\n🟢 BUY signals: {len(buys)}")
    for r in buys:
        print(f"   → {r['name']} ({r['set']}) — ${r['tcg_market']:,.2f} | {r['cm_trend']:+.1f}% CM")

    # ── Save ──────────────────────────────────────────────────
    output = {
        'generated':       datetime.now().isoformat(),
        'model_version':   '3',
        'db_powered':      True,
        'total_analyzed':  len(results),
        'db_cards_scored': len(db_cards),
        'top25':           top25,
        'all_results':     results,
    }
    with open(RESULTS_V3, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved → {RESULTS_V3}")
    print(f"Total analyzed: {len(results)} ({len(db_cards)} from DB + {len(SEALED)} sealed)")
    return top25

if __name__ == '__main__':
    run()
