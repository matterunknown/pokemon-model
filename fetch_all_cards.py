#!/usr/bin/env python3
"""
Vessel Pokemon — Full Card Database Builder
Fetches all cards from Pokemon TCG API, scores them, writes to SQLite.
Runs nightly. Powers the advisor at scale.
"""

import json
import sqlite3
import time
import requests
from datetime import datetime
from pathlib import Path

DB_PATH = Path('/opt/orchid/apps/pokemon-model/db/cards.db')
API_BASE = 'https://api.pokemontcg.io/v2'
PAGE_SIZE = 250

# ── Set metadata for scoring context ─────────────────────────────
SET_ERA = {
    # Wizards era — highest vintage value
    'base1':'wizards','base2':'wizards','base3':'wizards','base4':'wizards',
    'base5':'wizards','base6':'wizards','gym1':'wizards','gym2':'wizards',
    'neo1':'wizards','neo2':'wizards','neo3':'wizards','neo4':'wizards',
    'si1':'wizards','sk2':'wizards',  # Aquapolis, Skyridge — e-Card era
    # Nintendo/EX era
    'ecard1':'nintendo','ecard2':'nintendo','ecard3':'nintendo',
    'ex1':'nintendo','ex2':'nintendo','ex3':'nintendo','ex4':'nintendo',
    'ex5':'nintendo','ex6':'nintendo','ex7':'nintendo','ex8':'nintendo',
    'ex9':'nintendo','ex10':'nintendo','ex11':'nintendo','ex12':'nintendo',
    'ex13':'nintendo','ex14':'nintendo','ex15':'nintendo','ex16':'nintendo',
    # DP era
    'dp1':'dp','dp2':'dp','dp3':'dp','dp4':'dp','dp5':'dp','dp6':'dp','dp7':'dp',
    'pl1':'dp','pl2':'dp','pl3':'dp','pl4':'dp',
    'hgss1':'dp','hgss2':'dp','hgss3':'dp','hgss4':'dp',
    # BW era
    'bw1':'bw','bw2':'bw','bw3':'bw','bw4':'bw','bw5':'bw','bw6':'bw',
    'bw7':'bw','bw8':'bw','bw9':'bw','bw10':'bw','bw11':'bw',
    # XY era
    'xy0':'xy','xy1':'xy','xy2':'xy','xy3':'xy','xy4':'xy','xy5':'xy',
    'xy6':'xy','xy7':'xy','xy8':'xy','xy9':'xy','xy10':'xy','xy11':'xy','xy12':'xy',
    'g1':'xy',  # Generations
    # SM era
    'sm1':'sm','sm2':'sm','sm3':'sm','sm4':'sm','sm35':'sm','sm5':'sm',
    'sm6':'sm','sm7':'sm','sm75':'sm','sm8':'sm','sm9':'sm','sm10':'sm',
    'sm11':'sm','sm115':'sm','sm12':'sm',
    'det1':'sm',  # Detective Pikachu
    # SWSH era
    'swsh1':'swsh','swsh2':'swsh','swsh3':'swsh','swsh35':'swsh','swsh4':'swsh',
    'swsh45':'swsh','swsh5':'swsh','swsh6':'swsh','swsh7':'swsh','swsh8':'swsh',
    'swsh9':'swsh','swsh10':'swsh','swsh10tg':'swsh','swsh11':'swsh',
    'swsh12':'swsh','swsh12pt5':'swsh',
    'cel25':'swsh','cel25c':'swsh',  # Celebrations
    'pgo':'swsh',  # Pokemon GO set
    # SV era
    'sv1':'sv','sv2':'sv','sv3':'sv','sv3pt5':'sv','sv4':'sv','sv4pt5':'sv',
    'sv5':'sv','sv6':'sv','sv6pt5':'sv','sv7':'sv','sv8':'sv','sv8pt5':'sv',
    'sv9':'sv',
    'svp':'sv',  # SV promos
    # Promos — assigned to parent era
    'swshp':'swsh','smp':'sm','xyp':'xy','bwp':'bw',
    'dpp':'dp','basep':'wizards','np':'nintendo',
    # New sets (Mega Evolution 2025+)
    'sv10':'sv','rsv10pt5':'sv','zsv10pt5':'sv',
    'me1':'sv','me2':'sv',
    # SWSH extras
    'swsh45sv':'swsh','swsh9tg':'swsh','swsh10tg':'swsh',
    'swsh11tg':'swsh','swsh12tg':'swsh','swsh12pt5gg':'swsh',
    # SM extras
    'sma':'sm','col1':'bw','dc1':'xy',
    # POP Series
    'pop1':'nintendo','pop2':'nintendo','pop3':'nintendo',
    'pop4':'dp','pop5':'dp','pop6':'dp','pop7':'dp','pop8':'dp','pop9':'dp',
    # McDonald's collections
    'mcd11':'bw','mcd12':'bw','mcd13':'xy','mcd14':'xy',
    'mcd15':'xy','mcd16':'xy','mcd19':'sm','mcd21':'swsh','mcd22':'swsh',
    'ru1':'nintendo',
}

ERA_MOMENTUM = {
    'wizards': 0.90,  # Peak vintage — always strong
    'nintendo': 0.75, # e-Card era especially undergraded
    'dp': 0.55,
    'bw': 0.50,
    'xy': 0.60,       # XY has some strong alts
    'sm': 0.65,       # SM rotation coming
    'swsh': 0.70,     # SWSH fully rotated — scarcity building
    'sv': 0.72,       # Current — active market
}

RARITY_SCORES = {
    # Vintage rarities
    'Rare Holo': 0.70,
    'Rare': 0.40,
    'Common': 0.10,
    'Uncommon': 0.15,
    # Modern rarities
    'Special Illustration Rare': 1.0,
    'Hyper Rare': 0.95,
    'Ultra Rare': 0.85,
    'Illustration Rare': 0.80,
    'Double Rare': 0.65,
    'Rare Holo V': 0.60,
    'Rare Holo VMAX': 0.65,
    'Rare Holo VSTAR': 0.65,
    'Rare Holo EX': 0.70,
    'Rare Ultra': 0.80,
    'Rare Secret': 0.85,
    'Rare Rainbow': 0.80,
    'Rare Shining': 0.90,  # Neo Shining cards
    'LEGEND': 0.75,
    'Trainer Gallery Rare Holo': 0.65,
    'Radiant Rare': 0.70,
    'Classic Collection': 0.75,
    'Shiny Rare': 0.60,
    'Shiny Ultra Rare': 0.85,
    'ACE SPEC Rare': 0.70,
}

# High-demand Pokemon get a score bonus
CHASE_POKEMON = {
    'Charizard': 0.20, 'Mewtwo': 0.15, 'Pikachu': 0.12, 'Umbreon': 0.15,
    'Gengar': 0.12, 'Lugia': 0.15, 'Ho-Oh': 0.12, 'Rayquaza': 0.10,
    'Eevee': 0.08, 'Mew': 0.12, 'Blastoise': 0.08, 'Venusaur': 0.08,
    'Espeon': 0.10, 'Vaporeon': 0.08, 'Jolteon': 0.07, 'Sylveon': 0.08,
    'Garchomp': 0.06, 'Gardevoir': 0.08, 'Dragapult': 0.06, 'Miraidon': 0.06,
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id          TEXT PRIMARY KEY,
        name        TEXT,
        set_id      TEXT,
        set_name    TEXT,
        series      TEXT,
        era         TEXT,
        rarity      TEXT,
        number      TEXT,
        supertype   TEXT,
        tcg_market  REAL,
        tcg_low     REAL,
        tcg_mid     REAL,
        tcg_high    REAL,
        cm_avg7     REAL,
        cm_avg30    REAL,
        cm_trend    REAL,
        cm_low      REAL,
        release_year INTEGER,
        image_small TEXT,
        image_large TEXT,
        score       REAL,
        signal      TEXT,
        score_rarity    REAL,
        score_era       REAL,
        score_price     REAL,
        score_momentum  REAL,
        score_chase     REAL,
        updated_at  TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sets (
        id          TEXT PRIMARY KEY,
        name        TEXT,
        series      TEXT,
        release_date TEXT,
        total       INTEGER,
        era         TEXT,
        updated_at  TEXT
    )''')

    c.execute('''CREATE INDEX IF NOT EXISTS idx_score ON cards(score DESC)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_name ON cards(name)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_set ON cards(set_id)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_signal ON cards(signal)''')
    conn.commit()
    return conn

def get_all_sets():
    sets = []
    r = requests.get(f'{API_BASE}/sets',
        params={'orderBy':'releaseDate','pageSize':250}, timeout=30)
    sets = r.json().get('data', [])
    print(f"  {len(sets)} sets fetched")
    return sets

def score_card(card_data, set_era, release_year):
    """Score a card 0-1 based on available signals."""
    name     = card_data.get('name', '')
    rarity   = card_data.get('rarity', '')
    supertype = card_data.get('supertype', '')
    tcp      = card_data.get('tcgplayer', {}).get('prices', {})
    cm       = card_data.get('cardmarket', {}).get('prices', {})

    # Skip trainer cards — not investment targets
    if supertype == 'Trainer':
        return None

    # Get best TCG price (try all price tiers)
    tcg_market = (
        tcp.get('holofoil', {}).get('market') or
        tcp.get('reverseHolofoil', {}).get('market') or
        tcp.get('unlimitedHolofoil', {}).get('market') or
        tcp.get('1stEditionHolofoil', {}).get('market') or
        tcp.get('normal', {}).get('market') or
        tcp.get('unlimited', {}).get('market') or
        0
    )
    tcg_low = (
        tcp.get('holofoil', {}).get('low') or
        tcp.get('unlimitedHolofoil', {}).get('low') or
        tcp.get('1stEditionHolofoil', {}).get('low') or
        tcp.get('normal', {}).get('low') or
        0
    )
    tcg_mid = (
        tcp.get('holofoil', {}).get('mid') or
        tcp.get('unlimitedHolofoil', {}).get('mid') or
        tcp.get('normal', {}).get('mid') or
        0
    )
    tcg_high = (
        tcp.get('holofoil', {}).get('high') or
        tcp.get('unlimitedHolofoil', {}).get('high') or
        tcp.get('normal', {}).get('high') or
        0
    )
    cm_avg7  = cm.get('avg7') or 0
    cm_avg30 = cm.get('avg30') or 0
    cm_low   = cm.get('lowPrice') or cm.get('lowPriceExPlus') or 0
    cm_trend_pct = ((cm_avg7 - cm_avg30) / cm_avg30 * 100) if cm_avg7 and cm_avg30 else 0

    # Skip cards with no price data and low rarity
    if tcg_market < 1 and cm_avg7 < 1 and rarity not in RARITY_SCORES:
        return None

    # ── Score dimensions ─────────────────────────────────────
    # 1. Rarity score
    s_rarity = RARITY_SCORES.get(rarity, 0.20)

    # 2. Era/momentum score
    s_era = ERA_MOMENTUM.get(set_era, 0.50)

    # 3. Price signal — cards with real market prices score higher
    price = tcg_market or cm_avg7 or 0
    if price >= 500:   s_price = 1.0
    elif price >= 200: s_price = 0.90
    elif price >= 100: s_price = 0.80
    elif price >= 50:  s_price = 0.70
    elif price >= 20:  s_price = 0.60
    elif price >= 10:  s_price = 0.50
    elif price >= 3:   s_price = 0.35
    elif price >= 1:   s_price = 0.20
    else:              s_price = 0.05

    # 4. Cardmarket momentum
    if cm_trend_pct > 30:   s_mom = 1.0
    elif cm_trend_pct > 15: s_mom = 0.85
    elif cm_trend_pct > 5:  s_mom = 0.70
    elif cm_trend_pct > 0:  s_mom = 0.55
    elif cm_trend_pct > -5: s_mom = 0.45
    elif cm_trend_pct > -15:s_mom = 0.30
    else:                    s_mom = 0.15

    # 5. Chase Pokemon bonus
    s_chase = 0.0
    for pokemon, bonus in CHASE_POKEMON.items():
        if pokemon.lower() in name.lower():
            s_chase = bonus
            break

    # Composite (weighted)
    composite = (
        s_rarity * 0.30 +
        s_era    * 0.20 +
        s_price  * 0.25 +
        s_mom    * 0.15 +
        min(s_chase, 0.20) * 0.10  # chase bonus capped at 10% weight
    )
    composite = min(round(composite, 3), 1.0)

    signal = (
        'BUY'   if composite >= 0.72 else
        'WATCH' if composite >= 0.58 else
        'HOLD'  if composite >= 0.42 else
        'AVOID'
    )

    return {
        'tcg_market': round(tcg_market, 2),
        'tcg_low':    round(tcg_low, 2),
        'tcg_mid':    round(tcg_mid, 2),
        'tcg_high':   round(tcg_high, 2),
        'cm_avg7':    round(cm_avg7, 2),
        'cm_avg30':   round(cm_avg30, 2),
        'cm_trend':   round(cm_trend_pct, 1),
        'cm_low':     round(cm_low, 2),
        'score':      composite,
        'signal':     signal,
        's_rarity':   round(s_rarity, 3),
        's_era':      round(s_era, 3),
        's_price':    round(s_price, 3),
        's_mom':      round(s_mom, 3),
        's_chase':    round(s_chase, 3),
    }

def fetch_set_cards(set_id, conn):
    """Fetch all cards for a set and upsert into DB."""
    page = 1
    total_fetched = 0

    while True:
        try:
            r = requests.get(f'{API_BASE}/cards',
                params={
                    'q': f'set.id:{set_id}',
                    'pageSize': PAGE_SIZE,
                    'page': page,
                    'orderBy': 'number',
                },
                timeout=20)

            if r.status_code == 429:
                print(f"    Rate limited — waiting 10s...")
                time.sleep(10)
                continue

            data = r.json()
            cards = data.get('data', [])
            if not cards:
                break

            now = datetime.now().isoformat()
            c = conn.cursor()

            for card in cards:
                s = card.get('set', {})
                set_era = SET_ERA.get(set_id, 'unknown')
                release_year = int(s.get('releaseDate', '2000')[:4])
                images = card.get('images', {})

                scored = score_card(card, set_era, release_year)
                if not scored:
                    continue

                c.execute('''INSERT OR REPLACE INTO cards VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )''', (
                    card['id'],
                    card.get('name', ''),
                    set_id,
                    s.get('name', ''),
                    s.get('series', ''),
                    set_era,
                    card.get('rarity', ''),
                    card.get('number', ''),
                    card.get('supertype', ''),
                    scored['tcg_market'],
                    scored['tcg_low'],
                    scored['tcg_mid'],
                    scored['tcg_high'],
                    scored['cm_avg7'],
                    scored['cm_avg30'],
                    scored['cm_trend'],
                    scored['cm_low'],
                    release_year,
                    images.get('small', ''),
                    images.get('large', ''),
                    scored['score'],
                    scored['signal'],
                    scored['s_rarity'],
                    scored['s_era'],
                    scored['s_price'],
                    scored['s_mom'],
                    scored['s_chase'],
                    now,
                ))

            conn.commit()
            total_fetched += len(cards)
            total_count = data.get('totalCount', 0)

            if total_fetched >= total_count:
                break
            page += 1
            time.sleep(0.3)  # Be nice to the API

        except Exception as e:
            print(f"    Error fetching {set_id} page {page}: {e}")
            time.sleep(2)
            break

    return total_fetched

def run():
    print(f"\n{'='*60}")
    print(f"Vessel Pokemon — Full Card Database Build")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db()

    print("Fetching all sets...")
    sets = get_all_sets()

    # Upsert sets
    c = conn.cursor()
    for s in sets:
        sid = s['id']
        c.execute('INSERT OR REPLACE INTO sets VALUES (?,?,?,?,?,?,?)', (
            sid, s['name'], s.get('series',''),
            s.get('releaseDate',''), s.get('total',0),
            SET_ERA.get(sid, 'unknown'),
            datetime.now().isoformat()
        ))
    conn.commit()
    print(f"  {len(sets)} sets saved\n")

    # Fetch cards set by set
    total_cards = 0
    for i, s in enumerate(sets):
        sid  = s['id']
        name = s['name']
        count = fetch_set_cards(sid, conn)
        total_cards += count
        print(f"  [{i+1:3}/{len(sets)}] {name:40} {count:4} cards")
        time.sleep(0.5)

    # Final stats
    c.execute('SELECT COUNT(*) FROM cards')
    db_count = c.fetchone()[0]
    c.execute('SELECT signal, COUNT(*) FROM cards GROUP BY signal ORDER BY COUNT(*) DESC')
    signals = c.fetchall()
    c.execute('SELECT COUNT(*) FROM cards WHERE score >= 0.72')
    buy_count = c.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"Database complete")
    print(f"  Total cards in DB: {db_count:,}")
    print(f"  BUY signals: {buy_count:,}")
    for sig, cnt in signals:
        print(f"  {sig}: {cnt:,}")

    # Save summary
    summary = {
        'generated': datetime.now().isoformat(),
        'total_cards': db_count,
        'signals': {sig: cnt for sig, cnt in signals},
        'sets': len(sets),
    }
    with open('/opt/orchid/apps/pokemon-model/db/summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nDB → /opt/orchid/apps/pokemon-model/db/cards.db")
    conn.close()

if __name__ == '__main__':
    run()

def post_build():
    """Auto-chain: runs after DB build completes."""
    import subprocess as sp
    print("\nAuto-chaining model run...")
    r = sp.run(['python3', '/opt/orchid/apps/pokemon-model/model_v3.py'], capture_output=True, text=True)
    if r.returncode == 0:
        print(r.stdout[-400:])
        print("Rebuilding page...")
        r2 = sp.run(['python3', '/opt/orchid/apps/pokemon-model/rebuild_page.py'], capture_output=True, text=True)
        print(r2.stdout[-200:] or r2.stderr[-100:])
    else:
        print(f"Model failed: {r.stderr[-200:]}")
