
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime


def get_ebay_sold(card_name: str, set_name: str, grade: str = "PSA 9") -> dict:
    """
    Scrape eBay sold listings for a graded Pokemon card.
    Returns: avg price, num sales, price trend, min, max
    """
    query = f"{card_name} {set_name} {grade} pokemon"
    encoded = urllib.parse.quote(query)
    url = (
        f"https://www.ebay.com/sch/i.html?_nkw={encoded}"
        f"&_sacat=0&LH_Sold=1&LH_Complete=1&_sop=13"  # sold, completed, newest first
    )
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        # Extract sold prices using regex
        # eBay sold prices appear in s-item__price spans
        prices = []
        
        # Pattern for sold prices
        price_patterns = [
            r'class="s-item__price"[^>]*>\s*\$([0-9,]+\.?[0-9]*)',
            r'"soldPrice"[^>]*>\s*\$([0-9,]+\.?[0-9]*)',
            r's-item__price.*?\$([0-9]+\.[0-9]{2})',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, html)
            for m in matches:
                try:
                    price = float(m.replace(",", ""))
                    # Filter out obviously wrong prices (< $1 or > $10k)
                    if 1 < price < 10000:
                        prices.append(price)
                except:
                    continue
            if prices:
                break
        
        # Also try JSON-LD data
        json_prices = re.findall(r'"price":"([0-9.]+)"', html)
        for p in json_prices:
            try:
                price = float(p)
                if 1 < price < 10000:
                    prices.append(price)
            except:
                continue
        
        # Deduplicate and filter
        prices = list(set(prices))
        
        if not prices:
            return {"error": "no_prices_found", "url": url}
        
        # Remove outliers (beyond 2 std devs)
        if len(prices) > 4:
            avg = sum(prices) / len(prices)
            std = (sum((p - avg) ** 2 for p in prices) / len(prices)) ** 0.5
            prices = [p for p in prices if abs(p - avg) <= 2 * std]
        
        prices.sort()
        avg_price = sum(prices) / len(prices)
        
        # Simple trend: compare first half vs second half of results
        mid = len(prices) // 2
        if mid > 0:
            first_half_avg = sum(prices[:mid]) / mid
            second_half_avg = sum(prices[mid:]) / (len(prices) - mid)
            # eBay newest first, so second half = older sales
            # If first_half (newer) > second_half (older), price is rising
            trend_pct = ((first_half_avg - second_half_avg) / max(second_half_avg, 1)) * 100
        else:
            trend_pct = 0
        
        return {
            "avg_price": round(avg_price, 2),
            "min_price": round(min(prices), 2),
            "max_price": round(max(prices), 2),
            "num_sales": len(prices),
            "trend_pct": round(trend_pct, 1),
            "trend": "rising" if trend_pct > 5 else "falling" if trend_pct < -5 else "stable",
            "prices": sorted(prices),
            "grade": grade,
        }
    
    except Exception as e:
        return {"error": str(e)}


def get_raw_price(card_name: str, set_name: str) -> dict:
    """Get ungraded (raw) card prices from eBay."""
    return get_ebay_sold(card_name, set_name, grade="ungraded")
