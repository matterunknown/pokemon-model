#!/usr/bin/env python3
"""Fetches only the sets that have 0 cards in the DB — fills gaps from timeouts."""

import sqlite3, time, requests, json
from datetime import datetime
from pathlib import Path

DB_PATH  = '/opt/orchid/apps/pokemon-model/db/cards.db'
API_BASE = 'https://api.pokemontcg.io/v2'
PAGE_SIZE = 250

# Import scoring and era data from main script
import sys
sys.path.insert(0, '/opt/orchid/apps/pokemon-model')
from fetch_all_cards import SET_ERA, ERA_MOMENTUM, score_card, init_db

def get_missing_sets(conn):
    c = conn.cursor()
    c.execute('''SELECT s.id, s.name FROM sets s
                 LEFT JOIN cards ca ON s.id = ca.set_id
                 GROUP BY s.id HAVING COUNT(ca.id) = 0
                 ORDER BY s.release_date''')
    return c.fetchall()

def fetch_set(set_id, conn):
    """Fetch a single set with retry logic."""
    page = 0
    total_saved = 0
    c = conn.cursor()
    now = datetime.now().isoformat()

    while True:
        page += 1
        for attempt, wait in enumerate([0, 8, 20, 45]):
            if wait: 
                print(f"      Retry {attempt}/3 in {wait}s...")
                time.sleep(wait)
            try:
                r = requests.get(f'{API_BASE}/cards',
                    params={'q': f'set.id:{set_id}', 'pageSize': PAGE_SIZE,
                            'page': page, 'orderBy': 'number'},
                    timeout=30)
                if r.status_code == 429:
                    print(f"      Rate limited — waiting 30s...")
                    time.sleep(30)
                    continue
                if r.status_code != 200:
                    print(f"      HTTP {r.status_code}")
                    break
                data = r.json()
                cards = data.get('data', [])
                if not cards:
                    return total_saved

                set_era = SET_ERA.get(set_id, 'unknown')
                release_year = 2000

                for card in cards:
                    s = card.get('set', {})
                    release_year = int(s.get('releaseDate', '2000')[:4])
                    images = card.get('images', {})
                    scored = score_card(card, set_era, release_year)
                    if not scored:
                        continue
                    c.execute('''INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        card['id'], card.get('name',''), set_id, s.get('name',''),
                        s.get('series',''), set_era, card.get('rarity',''),
                        card.get('number',''), card.get('supertype',''),
                        scored['tcg_market'], scored['tcg_low'], scored['tcg_mid'],
                        scored['tcg_high'], scored['cm_avg7'], scored['cm_avg30'],
                        scored['cm_trend'], scored['cm_low'], release_year,
                        images.get('small',''), images.get('large',''),
                        scored['score'], scored['signal'],
                        scored['s_rarity'], scored['s_era'], scored['s_price'],
                        scored['s_mom'], scored['s_chase'], now,
                    ))

                conn.commit()
                total_saved += len(cards)
                total_count = data.get('totalCount', 0)
                if total_saved >= total_count:
                    return total_saved
                break  # success — next page

            except Exception as e:
                if attempt == 3:
                    print(f"      Failed after 3 retries: {e}")
                    return total_saved
                continue
        else:
            return total_saved
        time.sleep(0.8)

def run():
    print(f"\n{'='*55}")
    print(f"Vessel Pokemon — Fill Missing Sets")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    missing = get_missing_sets(conn)
    print(f"Missing sets: {len(missing)}\n")

    total_added = 0
    for i, (set_id, set_name) in enumerate(missing):
        print(f"  [{i+1:2}/{len(missing)}] {set_name:35} ", end='', flush=True)
        count = fetch_set(set_id, conn)
        print(f"{count} cards")
        total_added += count
        time.sleep(1.2)

    conn.cursor().execute('SELECT COUNT(*) FROM cards')
    final_total = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
    conn.close()

    print(f"\nAdded: {total_added:,} cards")
    print(f"Total in DB: {final_total:,}")

    # Save summary
    sigs = {}
    conn2 = sqlite3.connect(DB_PATH)
    for row in conn2.execute('SELECT signal, COUNT(*) FROM cards GROUP BY signal'):
        sigs[row[0]] = row[1]
    conn2.close()

    summary = {'generated': datetime.now().isoformat(), 'total_cards': final_total, 'signals': sigs, 'sets': 172}
    with open('/opt/orchid/apps/pokemon-model/db/summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    # Chain model + page rebuild
    import subprocess as sp
    print("\nRunning model v3...")
    r = sp.run(['python3','/opt/orchid/apps/pokemon-model/model_v3.py'], capture_output=True, text=True)
    print(r.stdout[-600:] if r.returncode == 0 else f"Error: {r.stderr[-200:]}")

    print("Rebuilding page...")
    r2 = sp.run(['python3','/opt/orchid/apps/pokemon-model/rebuild_page.py'], capture_output=True, text=True)
    print(r2.stdout[-200:] or r2.stderr[-100:])
    print("Done.")

if __name__ == '__main__':
    run()
