#!/usr/bin/env python3
"""
Vessel Pokemon Acquisition Model v2
Live price data from TCGplayer + Cardmarket trend signals.
"""

import json
import time
import requests
from datetime import datetime

# ── PSA Population data (known values) ────────────────────────
PSA_POP = {
    ("Lugia", "Neo Genesis"):          {"psa9": 812,  "psa10": 156, "total": 4821},
    ("Ho-Oh", "Neo Revelation"):       {"psa9": 234,  "psa10": 45,  "total": 1456},
    ("Suicune", "Neo Revelation"):     {"psa9": 445,  "psa10": 89,  "total": 2341},
    ("Entei", "Neo Revelation"):       {"psa9": 312,  "psa10": 67,  "total": 1876},
    ("Raikou", "Neo Revelation"):      {"psa9": 289,  "psa10": 54,  "total": 1654},
    ("Shining Charizard", "Neo Destiny"): {"psa9": 89, "psa10": 12, "total": 654},
    ("Shining Mewtwo", "Neo Destiny"):    {"psa9": 134,"psa10": 23,  "total": 876},
    ("Dark Charizard", "Team Rocket"):    {"psa9": 523,"psa10": 98,  "total": 3241},
    ("Dark Blastoise", "Team Rocket"):    {"psa9": 412,"psa10": 76,  "total": 2654},
    ("Gengar", "Fossil"):              {"psa9": 678,  "psa10": 134, "total": 4123},
    ("Lapras", "Fossil"):              {"psa9": 534,  "psa10": 112, "total": 3234},
    ("Articuno", "Fossil"):            {"psa9": 456,  "psa10": 89,  "total": 2876},
    ("Scyther", "Jungle"):             {"psa9": 789,  "psa10": 167, "total": 4567},
    ("Vaporeon", "Jungle"):            {"psa9": 456,  "psa10": 98,  "total": 2876},
    ("Blaine's Charizard", "Gym Challenge"): {"psa9": 187, "psa10": 23, "total": 1234},
    ("Giovanni's Nidoking", "Gym Challenge"): {"psa9": 156,"psa10": 18, "total": 987},
}

# ── Grading cost estimate ──────────────────────────────────────
# PSA standard tier ~$25-50 per card + shipping
GRADING_COST = 50  # Conservative estimate

def get_card_prices(name: str, set_name: str) -> dict:
    """Fetch live prices from Pokemon TCG API."""
    try:
        r = requests.get(
            "https://api.pokemontcg.io/v2/cards",
            params={"q": f'name:"{name}"', "pageSize": 20},
            timeout=10
        )
        cards = r.json().get("data", [])
        matches = [c for c in cards if set_name.lower() in c.get("set", {}).get("name", "").lower()]
        if not matches:
            return {}
        c = matches[0]
        tcp = c.get("tcgplayer", {}).get("prices", {})
        cm  = c.get("cardmarket", {}).get("prices", {})

        tcg_market = (
            tcp.get("holofoil", {}).get("market") or
            tcp.get("unlimitedHolofoil", {}).get("market") or
            tcp.get("1stEditionHolofoil", {}).get("market") or
            tcp.get("normal", {}).get("market") or 0
        )
        tcg_low = (
            tcp.get("holofoil", {}).get("low") or
            tcp.get("unlimitedHolofoil", {}).get("low") or 0
        )
        cm_avg7  = cm.get("avg7") or 0
        cm_avg30 = cm.get("avg30") or 0
        cm_trend = ((cm_avg7 - cm_avg30) / max(cm_avg30, 1) * 100) if cm_avg7 and cm_avg30 else 0

        return {
            "tcg_market": round(tcg_market, 2),
            "tcg_low": round(tcg_low, 2),
            "cm_avg7": round(cm_avg7, 2),
            "cm_avg30": round(cm_avg30, 2),
            "cm_trend_pct": round(cm_trend, 1),
            "image": c.get("images", {}).get("large"),
            "rarity": c.get("rarity"),
        }
    except Exception as e:
        return {"error": str(e)}


def score_card(name: str, set_name: str, prices: dict, pop: dict) -> dict:
    """Score a card across 6 dimensions."""

    tcg = prices.get("tcg_market") or 0
    tcg_low = prices.get("tcg_low") or 0
    cm_trend = prices.get("cm_trend_pct") or 0
    psa9  = pop.get("psa9", 500)
    psa10 = pop.get("psa10", 80)
    total = pop.get("total", 3000)

    # Raw price estimate: use TCGplayer low as proxy for raw price
    # Raw typically trades at 10-20% of PSA 9 value
    raw_est = tcg_low * 0.12 if tcg_low else tcg * 0.12

    # ── 1. SCARCITY ───────────────────────────────────────────
    scarcity = (
        1.0 if psa9 < 50 else
        0.9 if psa9 < 100 else
        0.8 if psa9 < 200 else
        0.7 if psa9 < 350 else
        0.6 if psa9 < 500 else
        0.5 if psa9 < 700 else
        0.3 if psa9 < 1000 else 0.1
    )
    # Bonus: PSA 10 is very hard to find
    if psa10 > 0 and (psa10 / max(psa9, 1)) < 0.15:
        scarcity = min(scarcity + 0.1, 1.0)

    # ── 2. ENTRY COST ─────────────────────────────────────────
    # Score based on raw acquisition cost (including grading)
    all_in = raw_est + GRADING_COST
    entry = (
        1.0 if all_in < 75 else
        0.9 if all_in < 100 else
        0.8 if all_in < 150 else
        0.7 if all_in < 200 else
        0.5 if all_in < 300 else
        0.3 if all_in < 500 else
        0.1
    )
    if tcg == 0:  # No price data
        entry = 0.5

    # ── 3. GRADE PREMIUM ──────────────────────────────────────
    # Estimate PSA 10 value as multiple of PSA 9
    # Lower PSA 10 pop = higher multiplier
    p10_multiplier = min(10, max(2, 200 / max(psa10, 1)))
    est_psa10 = tcg * p10_multiplier
    if tcg > 0:
        premium_pct = (est_psa10 - tcg) / tcg * 100
        grade_premium = (
            1.0 if premium_pct > 700 else
            0.9 if premium_pct > 500 else
            0.8 if premium_pct > 300 else
            0.6 if premium_pct > 150 else
            0.4
        )
    else:
        grade_premium = 0.5

    # ── 4. MOMENTUM ───────────────────────────────────────────
    # Combine Cardmarket 7v30 trend + set-level momentum
    SET_MOMENTUM = {
        "Neo Genesis": 0.65,
        "Neo Revelation": 0.85,  # Gen 2 dogs actively rising
        "Neo Destiny": 0.90,     # Shining cards very early
        "Team Rocket": 0.65,
        "Gym Heroes": 0.70,
        "Gym Challenge": 0.75,
        "Fossil": 0.55,
        "Jungle": 0.55,
        "Skyridge": 0.95,
        "Aquapolis": 0.95,
    }
    set_mom = SET_MOMENTUM.get(set_name, 0.5)

    # Add live Cardmarket trend signal
    if cm_trend > 50:
        trend_bonus = 0.20
    elif cm_trend > 20:
        trend_bonus = 0.12
    elif cm_trend > 5:
        trend_bonus = 0.06
    elif cm_trend < -20:
        trend_bonus = -0.10
    elif cm_trend < -5:
        trend_bonus = -0.05
    else:
        trend_bonus = 0.0

    momentum = min(max(set_mom + trend_bonus, 0.0), 1.0)

    # ── 5. LIQUIDITY ──────────────────────────────────────────
    liquidity = (
        0.9 if total > 5000 else
        0.8 if total > 3000 else
        0.7 if total > 1500 else
        0.5 if total > 500 else
        0.3 if total > 200 else 0.2
    )

    # ── 6. VALUE (ROI potential) ───────────────────────────────
    # If we grade a PSA 9, what's the return after costs?
    if tcg > 0 and raw_est > 0:
        roi = (tcg - all_in) / all_in
        value = (
            1.0 if roi > 5.0 else
            0.9 if roi > 3.0 else
            0.8 if roi > 2.0 else
            0.7 if roi > 1.0 else
            0.5 if roi > 0.5 else
            0.3 if roi > 0 else 0.1
        )
    else:
        value = 0.5

    # ── COMPOSITE (weighted) ──────────────────────────────────
    weights = {
        "scarcity":      0.25,
        "entry":         0.20,
        "grade_premium": 0.15,
        "momentum":      0.20,
        "liquidity":     0.10,
        "value":         0.10,
    }
    composite = (
        scarcity      * weights["scarcity"]      +
        entry         * weights["entry"]         +
        grade_premium * weights["grade_premium"] +
        momentum      * weights["momentum"]      +
        liquidity     * weights["liquidity"]     +
        value         * weights["value"]
    )

    signal = (
        "BUY"   if composite >= 0.78 else
        "WATCH" if composite >= 0.68 else
        "HOLD"  if composite >= 0.55 else
        "AVOID"
    )

    return {
        "card": name,
        "set": set_name,
        "tcg_psa9_market": tcg,
        "tcg_low": tcg_low,
        "raw_estimate": round(raw_est, 2),
        "all_in_cost": round(all_in, 2),
        "cm_trend_pct": cm_trend,
        "psa9_pop": psa9,
        "psa10_pop": psa10,
        "total_graded": total,
        "scores": {
            "scarcity":      round(scarcity, 2),
            "entry_cost":    round(entry, 2),
            "grade_premium": round(grade_premium, 2),
            "momentum":      round(momentum, 2),
            "liquidity":     round(liquidity, 2),
            "value_roi":     round(value, 2),
        },
        "composite_score": round(composite, 3),
        "signal": signal,
        "image": prices.get("image"),
        "rarity": prices.get("rarity"),
    }


def run():
    print(f"\n{'='*72}")
    print(f"Vessel Pokemon Acquisition Model v2 — Live Data")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*72}\n")

    cards = list(PSA_POP.keys())
    results = []

    for name, set_name in cards:
        pop = PSA_POP[(name, set_name)]
        prices = get_card_prices(name, set_name)
        result = score_card(name, set_name, prices, pop)
        results.append(result)
        trend = f"{result['cm_trend_pct']:+.1f}%" if result['cm_trend_pct'] else "N/A"
        print(f"  {name:28} ({set_name:15}) | TCG=${result['tcg_psa9_market'] or 'N/A':<8} | Trend:{trend:>7} | Score:{result['composite_score']:.3f} {result['signal']}")
        time.sleep(0.3)

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    # Save
    with open("/opt/orchid/apps/pokemon-model/results_v2.json", "w") as f:
        json.dump({"generated": datetime.now().isoformat(), "results": results}, f, indent=2)

    print(f"\n{'='*72}")
    print(f"RANKED ACQUISITION LIST")
    print(f"{'='*72}")
    print(f"{'#':<3} {'Sig':<7} {'Score':<7} {'Card':<28} {'Set':<16} {'TCG PSA9':<10} {'Raw+Grade':<11} {'CM Trend'}")
    print(f"{'-'*3} {'-'*7} {'-'*7} {'-'*28} {'-'*16} {'-'*10} {'-'*11} {'-'*9}")

    for i, r in enumerate(results):
        icon = {"BUY":"🟢","WATCH":"🟡","HOLD":"⚪","AVOID":"🔴"}.get(r["signal"],"")
        raw = f"${r['all_in_cost']:.0f}" if r['all_in_cost'] else "N/A"
        tcg = f"${r['tcg_psa9_market']:.0f}" if r['tcg_psa9_market'] else "N/A"
        trend = f"{r['cm_trend_pct']:+.1f}%" if r['cm_trend_pct'] else "N/A"
        print(f"{i+1:<3} {icon}{r['signal']:<6} {r['composite_score']:<7.3f} {r['card']:<28} {r['set']:<16} {tcg:<10} {raw:<11} {trend}")

    buys   = [r for r in results if r["signal"] == "BUY"]
    watches = [r for r in results if r["signal"] == "WATCH"]

    if buys:
        print(f"\n{'='*72}")
        print(f"🟢 BUY SIGNALS ({len(buys)})")
        print(f"{'='*72}")
        for r in buys:
            print(f"\n  {r['card']} — {r['set']}")
            print(f"  TCG PSA 9 market: ${r['tcg_psa9_market']}")
            print(f"  All-in cost (raw + grading): ${r['all_in_cost']:.0f}")
            print(f"  PSA 9 pop: {r['psa9_pop']} | PSA 10 pop: {r['psa10_pop']}")
            print(f"  CM 7-day trend: {r['cm_trend_pct']:+.1f}%")
            s = r["scores"]
            print(f"  Scores → Scarcity:{s['scarcity']} Entry:{s['entry_cost']} "
                  f"Momentum:{s['momentum']} GradePremium:{s['grade_premium']} "
                  f"Liquidity:{s['liquidity']} Value:{s['value_roi']}")

    print(f"\n{'='*72}")
    print(f"🟡 WATCH LIST ({len(watches)})")
    print(f"{'='*72}")
    for r in watches:
        print(f"  {r['card']:28} ({r['set']:16}) Score:{r['composite_score']:.3f} | TCG:${r['tcg_psa9_market'] or 'N/A'} | Trend:{r['cm_trend_pct']:+.1f}%")

    print(f"\nResults saved → /opt/orchid/apps/pokemon-model/results_v2.json")
    print(f"{'='*72}\n")
    return results

if __name__ == "__main__":
    run()
