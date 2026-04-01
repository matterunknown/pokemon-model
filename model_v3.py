#!/usr/bin/env python3
"""
Vessel Pokemon Acquisition Model v3
All-inclusive: vintage singles, modern singles, sealed product
Top 25 by composite score
"""

import json
import time
import requests
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CANDIDATE UNIVERSE
# ─────────────────────────────────────────────────────────────
CANDIDATES = [

    # ── VINTAGE SINGLES ──────────────────────────────────────
    {   "name": "Shining Charizard",   "set": "Neo Destiny",      "type": "vintage_single",
        "psa9_pop": 89,   "psa10_pop": 12,  "total_graded": 654,
        "set_momentum": 0.90, "reprint_risk": 0.0, "notes": "Shining era — extremely scarce, market undiscovered" },
    {   "name": "Shining Mewtwo",      "set": "Neo Destiny",      "type": "vintage_single",
        "psa9_pop": 134,  "psa10_pop": 23,  "total_graded": 876,
        "set_momentum": 0.90, "reprint_risk": 0.0, "notes": "Near 10x raw-to-PSA9 return, low pop" },
    {   "name": "Shining Gyarados",    "set": "Neo Destiny",      "type": "vintage_single",
        "psa9_pop": 78,   "psa10_pop": 11,  "total_graded": 521,
        "set_momentum": 0.90, "reprint_risk": 0.0, "notes": "Lowest pop of the Shining cards" },
    {   "name": "Shining Magikarp",    "set": "Neo Destiny",      "type": "vintage_single",
        "psa9_pop": 67,   "psa10_pop": 8,   "total_graded": 432,
        "set_momentum": 0.90, "reprint_risk": 0.0, "notes": "Lowest absolute pop in Neo Destiny" },
    {   "name": "Ho-Oh",               "set": "Neo Revelation",   "type": "vintage_single",
        "psa9_pop": 234,  "psa10_pop": 45,  "total_graded": 1456,
        "set_momentum": 0.85, "reprint_risk": 0.0, "notes": "Gen 2 nostalgia wave actively rising" },
    {   "name": "Raikou",              "set": "Neo Revelation",   "type": "vintage_single",
        "psa9_pop": 289,  "psa10_pop": 54,  "total_graded": 1654,
        "set_momentum": 0.85, "reprint_risk": 0.0, "notes": "Sacred beasts — strong 30d trend" },
    {   "name": "Entei",               "set": "Neo Revelation",   "type": "vintage_single",
        "psa9_pop": 312,  "psa10_pop": 67,  "total_graded": 1876,
        "set_momentum": 0.85, "reprint_risk": 0.0, "notes": "Lowest entry of the three beasts" },
    {   "name": "Suicune",             "set": "Neo Revelation",   "type": "vintage_single",
        "psa9_pop": 445,  "psa10_pop": 89,  "total_graded": 2341,
        "set_momentum": 0.85, "reprint_risk": 0.0, "notes": "Most liquid of the beasts" },
    {   "name": "Lugia",               "set": "Neo Genesis",      "type": "vintage_single",
        "psa9_pop": 812,  "psa10_pop": 156, "total_graded": 4821,
        "set_momentum": 0.65, "reprint_risk": 0.0, "notes": "Well known, high pop — CM trend negative" },
    {   "name": "Blaine's Charizard",  "set": "Gym Challenge",    "type": "vintage_single",
        "psa9_pop": 187,  "psa10_pop": 23,  "total_graded": 1234,
        "set_momentum": 0.80, "reprint_risk": 0.0, "notes": "110% CM 7d spike — set completion demand" },
    {   "name": "Dark Charizard",      "set": "Team Rocket",      "type": "vintage_single",
        "psa9_pop": 523,  "psa10_pop": 98,  "total_graded": 3241,
        "set_momentum": 0.65, "reprint_risk": 0.0, "notes": "Cult following, steady" },
    {   "name": "Charizard",           "set": "Skyridge",         "type": "vintage_single",
        "psa9_pop": 34,   "psa10_pop": 4,   "total_graded": 187,
        "set_momentum": 0.95, "reprint_risk": 0.0, "notes": "e-Card era — barely graded, first mover" },
    {   "name": "Lugia",               "set": "Aquapolis",        "type": "vintage_single",
        "psa9_pop": 45,   "psa10_pop": 6,   "total_graded": 234,
        "set_momentum": 0.95, "reprint_risk": 0.0, "notes": "Crystal Pokemon era, extremely undergraded" },
    {   "name": "Ho-Oh",               "set": "Aquapolis",        "type": "vintage_single",
        "psa9_pop": 38,   "psa10_pop": 5,   "total_graded": 198,
        "set_momentum": 0.95, "reprint_risk": 0.0, "notes": "Lowest pop Ho-Oh across all sets" },
    {   "name": "Gengar",              "set": "Fossil",           "type": "vintage_single",
        "psa9_pop": 678,  "psa10_pop": 134, "total_graded": 4123,
        "set_momentum": 0.60, "reprint_risk": 0.0, "notes": "Gengar tax — broadly popular Pokémon" },

    # ── MODERN SINGLES ───────────────────────────────────────
    {   "name": "Mega Gengar ex SIR",  "set": "Ascended Heroes",  "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 18, "set_momentum": 0.92, "reprint_risk": 0.35,
        "raw_market": 280, "psa10_multiplier": 2.5,
        "notes": "First Mega Gengar in 10 years. Centering issues = gem mint scarce. PSA 10 pre-selling at 2.5x raw." },
    {   "name": "Bubble Mew (Mew ex SIR 232)", "set": "Paldean Fates", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 12, "set_momentum": 0.75, "reprint_risk": 0.40,
        "raw_market": 700, "psa10_multiplier": 3.0,
        "notes": "ATH $700 Sept 2025, corrected, bounced back above $700. Wait for dip to $400-500." },
    {   "name": "Umbreon ex SIR 161",  "set": "Prismatic Evolutions", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 20, "set_momentum": 0.80, "reprint_risk": 0.50,
        "raw_market": 1005, "psa10_multiplier": 3.8,
        "notes": "Moonbreon successor. $3,850 PSA 10. Set reprinted heavily — raw supply high, gem mint hard." },
    {   "name": "Moonbreon (Umbreon VMAX Alt Art)", "set": "Evolving Skies", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 25, "set_momentum": 0.90, "reprint_risk": 0.10,
        "raw_market": 1771, "psa10_multiplier": 1.8,
        "notes": "449% long-term appreciation. Holds 80% value through corrections. Blue chip. High entry." },
    {   "name": "Team Rocket's Mewtwo ex SIR", "set": "Destined Rivals", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 15, "set_momentum": 0.88, "reprint_risk": 0.30,
        "raw_market": 500, "psa10_multiplier": 2.8,
        "notes": "Gen 1 nostalgia + Team Rocket. Listings under $500 dried up naturally — no buyout." },
    {   "name": "Mega Dragonite ex SIR", "set": "Ascended Heroes", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 20, "set_momentum": 0.85, "reprint_risk": 0.35,
        "raw_market": 180, "psa10_multiplier": 2.5,
        "notes": "Second chase of Ascended Heroes. Lower entry than Gengar, similar upside profile." },
    {   "name": "Crown Zenith Mew VSTAR Rainbow", "set": "Crown Zenith", "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 30, "set_momentum": 0.78, "reprint_risk": 0.20,
        "raw_market": 40, "psa10_multiplier": 9.0,
        "notes": "30th anniversary hype building. PSA 10s at $375+. 3-year-old set, supply drying up." },
    {   "name": "Gengar VMAX Alt Art",  "set": "Fusion Strike",    "type": "modern_single",
        "psa9_pop": 0, "psa10_pop": 0, "total_graded": 0,
        "pull_rate_boxes": 22, "set_momentum": 0.82, "reprint_risk": 0.15,
        "raw_market": 700, "psa10_multiplier": 2.0,
        "notes": "Gengar tax driving all Gengar alts. SWSH rotation amplifies scarcity." },

    # ── SEALED PRODUCT ───────────────────────────────────────
    {   "name": "Ascended Heroes ETB", "set": "Ascended Heroes",  "type": "sealed",
        "msrp": 65, "current_price": 108, "set_momentum": 0.92, "reprint_risk": 0.45,
        "chase_strength": 0.95, "supply_exclusivity": 0.5,
        "comp_set": "Prismatic Evolutions", "notes": "Prismatic Evolutions setup. Cases cheap now. Deep chase card lineup." },
    {   "name": "Destined Rivals ETB", "set": "Destined Rivals",  "type": "sealed",
        "msrp": 65, "current_price": 146, "set_momentum": 0.88, "reprint_risk": 0.30,
        "chase_strength": 0.85, "supply_exclusivity": 0.5,
        "comp_set": "Team Rocket", "notes": "Team Rocket nostalgia. Undervalued for the chase lineup quality." },
    {   "name": "Prismatic Evolutions ETB", "set": "Prismatic Evolutions", "type": "sealed",
        "msrp": 65, "current_price": 190, "set_momentum": 0.80, "reprint_risk": 0.55,
        "chase_strength": 0.95, "supply_exclusivity": 0.6,
        "comp_set": "Evolving Skies", "notes": "Already running. Reprinted heavily. Floor likely found." },
    {   "name": "Crown Zenith ETB",    "set": "Crown Zenith",     "type": "sealed",
        "msrp": 65, "current_price": 230, "set_momentum": 0.78, "reprint_risk": 0.10,
        "chase_strength": 0.80, "supply_exclusivity": 0.4,
        "comp_set": "SWSH era", "notes": "SWSH rotation locks in scarcity. 30th anniversary tailwind." },
    {   "name": "Evolving Skies ETB",  "set": "Evolving Skies",   "type": "sealed",
        "msrp": 65, "current_price": 2600, "set_momentum": 0.95, "reprint_risk": 0.05,
        "chase_strength": 1.0, "supply_exclusivity": 0.9,
        "comp_set": "Gold standard", "notes": "The comp all other sets are measured against. Ship has sailed on entry." },
]

GRADING_COST = 50

def get_tcg_price(name, set_name):
    """Fetch live TCGplayer price."""
    try:
        r = requests.get("https://api.pokemontcg.io/v2/cards",
            params={"q": f'name:"{name}"', "pageSize": 20}, timeout=10)
        cards = r.json().get("data", [])
        matches = [c for c in cards if set_name.lower() in c.get("set", {}).get("name", "").lower()]
        if not matches:
            return {}
        c = matches[0]
        tcp = c.get("tcgplayer", {}).get("prices", {})
        cm  = c.get("cardmarket", {}).get("prices", {})
        market = (tcp.get("holofoil", {}).get("market") or
                  tcp.get("unlimitedHolofoil", {}).get("market") or
                  tcp.get("1stEditionHolofoil", {}).get("market") or
                  tcp.get("normal", {}).get("market") or 0)
        low = (tcp.get("holofoil", {}).get("low") or
               tcp.get("unlimitedHolofoil", {}).get("low") or 0)
        cm7  = cm.get("avg7") or 0
        cm30 = cm.get("avg30") or 0
        trend = ((cm7 - cm30) / max(cm30, 1) * 100) if cm7 and cm30 else 0
        return {"market": round(market, 2), "low": round(low, 2),
                "cm_trend": round(trend, 1), "image": c.get("images", {}).get("large")}
    except:
        return {}

def score_vintage(card, prices):
    """Score a vintage single card."""
    psa9  = card["psa9_pop"]
    psa10 = card["psa10_pop"]
    total = card["total_graded"]
    market = prices.get("market") or 0
    low    = prices.get("low") or 0
    cm_trend = prices.get("cm_trend") or 0
    mom    = card["set_momentum"]

    raw_est = low * 0.12 if low else market * 0.12
    all_in  = raw_est + GRADING_COST

    # Scarcity
    scarcity = (1.0 if psa9<50 else 0.9 if psa9<100 else 0.8 if psa9<200
                else 0.7 if psa9<350 else 0.6 if psa9<500
                else 0.5 if psa9<700 else 0.3 if psa9<1000 else 0.1)
    if psa10 > 0 and (psa10/max(psa9,1)) < 0.15:
        scarcity = min(scarcity + 0.1, 1.0)

    # Entry
    entry = (1.0 if all_in<75 else 0.9 if all_in<100 else 0.8 if all_in<150
             else 0.7 if all_in<200 else 0.5 if all_in<300 else 0.3 if all_in<500 else 0.1)
    if market == 0: entry = 0.5

    # Grade premium
    p10_mult = min(10, max(2, 200/max(psa10,1)))
    est_psa10 = market * p10_mult
    if market > 0:
        prem_pct = (est_psa10 - market) / market * 100
        grade_prem = (1.0 if prem_pct>700 else 0.9 if prem_pct>500 else 0.8 if prem_pct>300
                      else 0.6 if prem_pct>150 else 0.4)
    else:
        grade_prem = 0.5

    # Momentum (set level + live CM trend)
    trend_bonus = (0.20 if cm_trend>50 else 0.12 if cm_trend>20 else 0.06 if cm_trend>5
                   else -0.10 if cm_trend<-20 else -0.05 if cm_trend<-5 else 0)
    momentum = min(max(mom + trend_bonus, 0), 1.0)

    # Liquidity
    liquidity = (0.9 if total>5000 else 0.8 if total>3000 else 0.7 if total>1500
                 else 0.5 if total>500 else 0.3 if total>200 else 0.2)

    # ROI
    if market > 0 and raw_est > 0:
        roi = (market - all_in) / all_in
        value = (1.0 if roi>5 else 0.9 if roi>3 else 0.8 if roi>2
                 else 0.7 if roi>1 else 0.5 if roi>0.5 else 0.3 if roi>0 else 0.1)
    else:
        value = 0.5

    composite = (scarcity*0.25 + entry*0.20 + grade_prem*0.15 +
                 momentum*0.20 + liquidity*0.10 + value*0.10)

    return {
        "scores": {"scarcity": round(scarcity,2), "entry": round(entry,2),
                   "grade_premium": round(grade_prem,2), "momentum": round(momentum,2),
                   "liquidity": round(liquidity,2), "value": round(value,2)},
        "composite": round(composite, 3),
        "tcg_market": market, "all_in_cost": round(all_in, 2),
        "cm_trend": cm_trend, "psa9_pop": psa9, "psa10_pop": psa10,
    }

def score_modern(card):
    """Score a modern single. Different model — PSA 10 is the play, not PSA 9."""
    raw    = card["raw_market"]
    p10x   = card["psa10_multiplier"]
    mom    = card["set_momentum"]
    reprint = card["reprint_risk"]
    pull   = card["pull_rate_boxes"]  # boxes to pull one

    # Entry cost relative to raw price
    entry = (1.0 if raw<100 else 0.9 if raw<200 else 0.7 if raw<400
             else 0.5 if raw<700 else 0.3 if raw<1200 else 0.1)

    # PSA 10 premium upside
    psa10_val = raw * p10x
    psa10_all_in = raw + GRADING_COST
    psa10_roi = (psa10_val - psa10_all_in) / psa10_all_in
    grade_prem = (1.0 if psa10_roi>5 else 0.9 if psa10_roi>3 else 0.8 if psa10_roi>2
                  else 0.6 if psa10_roi>1 else 0.4 if psa10_roi>0 else 0.2)

    # Pull rate scarcity proxy (higher boxes = scarcer)
    pull_score = (0.9 if pull>20 else 0.7 if pull>15 else 0.5 if pull>10 else 0.3)

    # Reprint risk (penalizes modern cards heavily)
    reprint_penalty = reprint * 0.4

    # Momentum
    momentum = min(max(mom - reprint_penalty, 0), 1.0)

    # Liquidity (modern cards are inherently liquid if popular)
    liquidity = 0.8 if raw > 200 else 0.6

    composite = (entry*0.20 + grade_prem*0.25 + pull_score*0.20 +
                 momentum*0.25 + liquidity*0.10)

    return {
        "scores": {"entry": round(entry,2), "grade_premium": round(grade_prem,2),
                   "pull_scarcity": round(pull_score,2), "momentum": round(momentum,2),
                   "liquidity": round(liquidity,2)},
        "composite": round(composite, 3),
        "tcg_market": raw, "all_in_cost": round(raw + GRADING_COST, 2),
        "psa10_est": round(raw * p10x, 2),
        "cm_trend": 0, "psa9_pop": 0, "psa10_pop": 0,
    }

def score_sealed(card):
    """Score sealed product. Hold thesis — buy sealed, hold as print run ends."""
    msrp    = card["msrp"]
    current = card["current_price"]
    mom     = card["set_momentum"]
    reprint = card["reprint_risk"]
    chase   = card["chase_strength"]
    excl    = card["supply_exclusivity"]

    # Premium over MSRP (lower = better entry)
    premium_mult = current / msrp
    entry = (1.0 if premium_mult<1.2 else 0.8 if premium_mult<1.5
             else 0.6 if premium_mult<2.0 else 0.3 if premium_mult<3.0 else 0.1)

    # Chase card strength (what's the floor if you open it)
    # Higher = more upside even if you open

    # Reprint risk
    reprint_score = 1.0 - reprint

    # Momentum (set desirability)
    # Exclusivity bonus (Pokemon Center exclusive, no booster box = harder to find)
    momentum = min(mom + (excl * 0.15), 1.0)

    # Long-term hold thesis
    hold_score = min(chase * reprint_score, 1.0)

    composite = (entry*0.25 + chase*0.20 + reprint_score*0.20 +
                 momentum*0.20 + hold_score*0.15)

    return {
        "scores": {"entry": round(entry,2), "chase_strength": round(chase,2),
                   "reprint_safety": round(reprint_score,2), "momentum": round(momentum,2),
                   "hold_thesis": round(hold_score,2)},
        "composite": round(composite, 3),
        "tcg_market": current, "all_in_cost": current,
        "msrp": msrp, "premium_pct": round((premium_mult-1)*100, 1),
        "cm_trend": 0, "psa9_pop": 0, "psa10_pop": 0,
    }

def run():
    print(f"\n{'='*70}")
    print(f"Vessel Pokemon Acquisition Model v3 — All Inclusive")
    print(f"Vintage singles · Modern singles · Sealed product")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*70}\n")

    results = []

    for card in CANDIDATES:
        ctype = card["type"]
        name  = f"{card['name']} ({card['set']})"

        if ctype == "vintage_single":
            prices = get_tcg_price(card["name"], card["set"])
            scored = score_vintage(card, prices)
            scored["image"] = prices.get("image")
            time.sleep(0.25)
        elif ctype == "modern_single":
            scored = score_modern(card)
            scored["image"] = None
        elif ctype == "sealed":
            scored = score_sealed(card)
            scored["image"] = None

        signal = ("BUY"   if scored["composite"] >= 0.78 else
                  "WATCH" if scored["composite"] >= 0.68 else
                  "HOLD"  if scored["composite"] >= 0.55 else "AVOID")

        result = {
            "rank": 0,
            "name": card["name"],
            "set": card["set"],
            "type": ctype,
            "signal": signal,
            "composite_score": scored["composite"],
            "tcg_market": scored["tcg_market"],
            "all_in_cost": scored["all_in_cost"],
            "cm_trend": scored.get("cm_trend", 0),
            "psa9_pop": scored.get("psa9_pop", 0),
            "psa10_pop": scored.get("psa10_pop", 0),
            "psa10_est": scored.get("psa10_est"),
            "msrp": scored.get("msrp"),
            "premium_pct": scored.get("premium_pct"),
            "scores": scored["scores"],
            "notes": card.get("notes", ""),
            "image": scored.get("image"),
        }
        results.append(result)
        trend_s = f"{scored.get('cm_trend',0):+.0f}%" if ctype == "vintage_single" else ""
        print(f"  [{ctype[:3].upper()}] {card['name']:30} {card['set']:22} {scored['composite']:.3f} {signal} {trend_s}")

    # Rank and take top 25
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    top25 = results[:25]

    # Save
    output = {
        "generated": datetime.now().isoformat(),
        "model_version": "3",
        "total_analyzed": len(results),
        "top25": top25,
        "all_results": results,
    }
    with open("/opt/orchid/apps/pokemon-model/results_v3.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*70}")
    print(f"TOP 25 ACQUISITION LIST")
    print(f"{'='*70}")
    TYPE_ICONS = {"vintage_single": "🏛️ ", "modern_single": "✨ ", "sealed": "📦 "}
    SIG_ICONS  = {"BUY": "🟢", "WATCH": "🟡", "HOLD": "⚪", "AVOID": "🔴"}
    for r in top25:
        icon = TYPE_ICONS.get(r["type"], "")
        sig  = SIG_ICONS.get(r["signal"], "")
        price = f"${r['tcg_market']:.0f}" if r['tcg_market'] else "N/A"
        print(f"  #{r['rank']:2} {sig}{r['signal']:<6} {r['composite_score']:.3f} {icon}{r['name']:28} {r['set']:22} {price}")

    buys = [r for r in top25 if r["signal"] == "BUY"]
    print(f"\n🟢 BUY SIGNALS: {len(buys)}")
    for r in buys:
        print(f"   → {r['name']} ({r['set']}) — Score {r['composite_score']:.3f} — {r['notes'][:60]}")

    print(f"\nFull results → /opt/orchid/apps/pokemon-model/results_v3.json")
    return top25

if __name__ == "__main__":
    run()
