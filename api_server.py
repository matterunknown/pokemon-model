#!/usr/bin/env python3
"""
Vessel Pokemon API — secure production version
- All SQL fully parameterized (no f-string injection)
- ORDER BY uses allowlist only
- No raw exceptions exposed to client
- CORS handled by nginx only (removed from server)
- Input sanitized and capped at server level
- Error responses generic
Runs on 127.0.0.1:8790 — nginx proxies externally
"""

import json
import sqlite3
import re
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime

DB_PATH = '/opt/orchid/apps/pokemon-model/db/cards.db'
PORT    = 8790

# Allowlists — never trust user input for structural SQL
ALLOWED_SORT   = {'score', 'price', 'name'}
ALLOWED_SIGNAL = {'BUY', 'WATCH', 'HOLD', 'AVOID'}
ALLOWED_ERA    = {'wizards','nintendo','dp','bw','xy','sm','swsh','sv','unknown'}
MAX_LIMIT      = 100
MAX_Q_LEN      = 100

logging.basicConfig(
    filename='/opt/orchid/apps/pokemon-model/api.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrent reads
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def sanitize_str(s, max_len=MAX_Q_LEN):
    """Strip dangerous characters, cap length."""
    if not s:
        return ''
    # Allow only alphanumeric, spaces, apostrophes, hyphens, dots
    s = re.sub(r"[^\w\s'\-\.\(\)]", '', s)
    return s[:max_len].strip()

def safe_int(val, default, min_val=1, max_val=MAX_LIMIT):
    try:
        return max(min_val, min(int(val), max_val))
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)

        # Log request (no user data in logs)
        logging.info(f"GET {path} from {self.client_address[0]}")

        try:
            if path == '/api/pokemon/search':
                self._search(params)
            elif path == '/api/pokemon/signals':
                self._signals(params)
            elif path == '/api/pokemon/sets':
                self._sets(params)
            elif path == '/api/pokemon/summary':
                self._summary()
            elif re.match(r'^/api/pokemon/card/[a-zA-Z0-9\-]+$', path):
                # Strict card ID format — only alphanumeric and hyphens
                card_id = path.split('/')[-1]
                self._card(card_id)
            else:
                self._error(404, "Not found")
        except Exception as e:
            logging.error(f"Request error on {path}: {e}", exc_info=True)
            self._error(500, "Internal error")

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')

        logging.info(f"POST {path} from {self.client_address[0]}")

        if path == '/api/pokemon/advisor':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length > 50000:  # 50KB max payload
                    self._error(413, "Payload too large")
                    return
                body = json.loads(self.rfile.read(length))
                self._advisor(body)
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON")
            except Exception as e:
                logging.error(f"Advisor error: {e}", exc_info=True)
                self._error(500, "Internal error")
        else:
            self._error(404, "Not found")

    def _search(self, params):
        # Sanitize all inputs
        q         = sanitize_str(params.get('q', [''])[0])
        limit     = safe_int(params.get('limit', [20])[0], 20, 1, MAX_LIMIT)
        min_price = safe_float(params.get('min_price', [0])[0])
        
        # Allowlist-validated params
        raw_era    = params.get('era', [None])[0]
        raw_sig    = params.get('signal', [None])[0]
        raw_sort   = params.get('sort', ['score'])[0]
        
        era    = raw_era.lower() if raw_era and raw_era.lower() in ALLOWED_ERA else None
        sig    = raw_sig.upper() if raw_sig and raw_sig.upper() in ALLOWED_SIGNAL else None
        sort   = raw_sort if raw_sort in ALLOWED_SORT else 'score'

        # ORDER BY uses allowlist — safe to interpolate
        order_col = {
            'score': 'score DESC',
            'price': 'tcg_market DESC',
            'name':  'name ASC',
        }[sort]

        # All WHERE clauses use ? placeholders — no injection possible
        sql  = '''SELECT id, name, set_id, set_name, era, rarity, number,
                         tcg_market, tcg_low, cm_avg7, cm_trend, cm_low,
                         release_year, image_small, score, signal,
                         score_rarity, score_era, score_price, score_momentum, score_chase
                  FROM cards WHERE 1=1'''
        args = []

        if q:
            sql  += ' AND (name LIKE ? OR set_name LIKE ?)'
            args += [f'%{q}%', f'%{q}%']
        if era:
            sql  += ' AND era = ?'
            args.append(era)
        if sig:
            sql  += ' AND signal = ?'
            args.append(sig)
        if min_price > 0:
            sql  += ' AND (tcg_market >= ? OR cm_avg7 >= ?)'
            args += [min_price, min_price]

        sql += ' AND (tcg_market > 0 OR cm_avg7 > 0 OR score >= 0.58)'
        sql += f' ORDER BY {order_col} LIMIT ?'
        args.append(limit)

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute(sql, args)
            rows = [dict(r) for r in c.fetchall()]
        finally:
            conn.close()

        self._json({'results': rows, 'count': len(rows), 'query': q})

    def _signals(self, params):
        raw_signal = params.get('signal', ['BUY'])[0].upper()
        signal = raw_signal if raw_signal in ALLOWED_SIGNAL else 'BUY'
        limit  = safe_int(params.get('limit', [50])[0], 50, 1, 250)
        raw_era = params.get('era', [None])[0]
        era    = raw_era.lower() if raw_era and raw_era.lower() in ALLOWED_ERA else None

        sql  = '''SELECT id, name, set_id, set_name, era, rarity,
                         tcg_market, tcg_low, cm_avg7, cm_trend,
                         image_small, score, signal, release_year
                  FROM cards WHERE signal = ?'''
        args = [signal]
        if era:
            sql += ' AND era = ?'
            args.append(era)
        sql += ' ORDER BY score DESC LIMIT ?'
        args.append(limit)

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute(sql, args)
            rows = [dict(r) for r in c.fetchall()]
        finally:
            conn.close()

        self._json({'signal': signal, 'results': rows, 'count': len(rows)})

    def _sets(self, params):
        raw_era = params.get('era', [None])[0]
        era     = raw_era.lower() if raw_era and raw_era.lower() in ALLOWED_ERA else None

        sql  = 'SELECT * FROM sets'
        args = []
        if era:
            sql += ' WHERE era = ?'
            args.append(era)
        sql += ' ORDER BY release_date DESC'

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute(sql, args)
            rows = [dict(r) for r in c.fetchall()]
        finally:
            conn.close()

        self._json({'sets': rows, 'count': len(rows)})

    def _card(self, card_id):
        # card_id already validated by regex in routing
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('SELECT * FROM cards WHERE id = ?', (card_id,))
            row = c.fetchone()
        finally:
            conn.close()

        if row:
            self._json(dict(row))
        else:
            self._error(404, "Card not found")

    def _summary(self):
        try:
            with open('/opt/orchid/apps/pokemon-model/db/summary.json') as f:
                self._json(json.load(f))
                return
        except FileNotFoundError:
            pass

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) as total FROM cards')
            total = c.fetchone()['total']
            c.execute('SELECT signal, COUNT(*) as cnt FROM cards GROUP BY signal')
            sigs = {r['signal']: r['cnt'] for r in c.fetchall()}
            c.execute('SELECT COUNT(*) as cnt FROM cards WHERE signal="BUY"')
            buys = c.fetchone()['cnt']
        finally:
            conn.close()

        self._json({
            'total_cards': total,
            'signals': sigs,
            'buy_signals': buys,
            'generated': datetime.now().isoformat(),
        })

    def _advisor(self, body):
        collection = body.get('collection', [])
        if not isinstance(collection, list):
            self._error(400, "collection must be a list")
            return
        if len(collection) > 500:  # sanity cap
            self._error(400, "Collection too large")
            return

        conn = get_db()
        try:
            c = conn.cursor()
            recognized   = []
            unrecognized = []

            for item in collection:
                if not isinstance(item, dict):
                    continue

                name     = sanitize_str(item.get('name', ''))
                set_name = sanitize_str(item.get('set_name', ''))

                if not name or len(name) < 2:
                    continue

                # Parameterized — safe
                if set_name:
                    c.execute('''SELECT id, name, set_id, set_name, era, rarity,
                                        tcg_market, tcg_low, cm_avg7, cm_trend, cm_low,
                                        image_small, score, signal, release_year
                                 FROM cards
                                 WHERE name LIKE ? AND set_name LIKE ?
                                 ORDER BY score DESC LIMIT 1''',
                              (f'%{name}%', f'%{set_name}%'))
                else:
                    c.execute('''SELECT id, name, set_id, set_name, era, rarity,
                                        tcg_market, tcg_low, cm_avg7, cm_trend, cm_low,
                                        image_small, score, signal, release_year
                                 FROM cards
                                 WHERE name LIKE ?
                                 ORDER BY score DESC LIMIT 1''',
                              (f'%{name}%',))

                row = c.fetchone()
                if row:
                    card_data = dict(row)
                    card_data['input_grade']  = sanitize_str(item.get('grade', 'unknown'), 20)
                    card_data['input_graded'] = bool(item.get('graded', False))
                    recognized.append(card_data)
                else:
                    unrecognized.append({'name': name, 'set_name': set_name})

            owned_ids  = tuple(r['id'] for r in recognized) or ('__none__',)
            owned_sets = list(set(r['set_id'] for r in recognized))[:5]
            recs       = []

            # Upgrade paths — parameterized
            for card in recognized:
                if (not card['input_graded'] and
                    card['signal'] in ('BUY', 'WATCH') and
                    card['tcg_market'] > 50):
                    recs.append({
                        'type': 'upgrade',
                        'priority': 1,
                        'card': card,
                        'reason': f"You own this raw — PSA 9 market ~${card['tcg_market']:.0f}. Strong grading candidate.",
                    })

            # Set completion — parameterized with tuple placeholder
            for set_id in owned_sets:
                placeholders = ','.join('?' * len(owned_ids))
                c.execute(f'''SELECT id, name, set_id, set_name, era, rarity,
                                     tcg_market, tcg_low, cm_avg7, cm_trend,
                                     image_small, score, signal
                              FROM cards
                              WHERE set_id = ?
                              AND id NOT IN ({placeholders})
                              AND signal IN ('BUY','WATCH')
                              ORDER BY score DESC LIMIT 5''',
                          (set_id,) + owned_ids)
                for row in c.fetchall():
                    recs.append({
                        'type': 'set_completion',
                        'priority': 2 if row['signal'] == 'BUY' else 3,
                        'card': dict(row),
                        'reason': f"Completes your {row['set_name']} collection. {row['signal']} signal, score {row['score']:.3f}.",
                    })

            # BUY gaps
            placeholders = ','.join('?' * len(owned_ids))
            c.execute(f'''SELECT id, name, set_id, set_name, era, rarity,
                                 tcg_market, tcg_low, cm_avg7, cm_trend,
                                 image_small, score, signal
                          FROM cards
                          WHERE signal = 'BUY'
                          AND id NOT IN ({placeholders})
                          ORDER BY score DESC LIMIT 10''',
                      owned_ids)
            for row in c.fetchall()[:5]:
                recs.append({
                    'type': 'gap_fill',
                    'priority': 2,
                    'card': dict(row),
                    'reason': f"Top BUY signal not in your collection. Score {row['score']:.3f}.",
                })

            # Diversification
            eras_owned = {r['era'] for r in recognized}
            if 'wizards' in eras_owned and 'sv' not in eras_owned:
                c.execute('''SELECT id, name, set_id, set_name, era, rarity,
                                    tcg_market, score, signal
                             FROM cards WHERE era='sv' AND signal='BUY'
                             ORDER BY score DESC LIMIT 1''')
                row = c.fetchone()
                if row:
                    recs.append({
                        'type': 'diversification',
                        'priority': 4,
                        'card': dict(row),
                        'reason': "Vintage-heavy collection — this modern card adds PSA 10 upside.",
                    })

            recs.sort(key=lambda x: (x['priority'], -x['card']['score']))

        finally:
            conn.close()

        self._json({
            'recognized':      recognized,
            'unrecognized':    unrecognized,
            'recommendations': recs[:20],
        })

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        # Security headers
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        # NOTE: CORS is handled by nginx — not set here
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, message):
        """Generic error — never expose internal details."""
        body = json.dumps({'error': message}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress default stdout logging — we use the file logger
        pass

if __name__ == '__main__':
    import sys
    print(f"Pokemon API starting on 127.0.0.1:{PORT}")
    print(f"DB: {DB_PATH}")
    print(f"Log: /opt/orchid/apps/pokemon-model/api.log")
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    server.serve_forever()
