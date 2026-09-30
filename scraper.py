import json
import re
import time
import random
from pathlib import Path
from datetime import datetime

import cloudscraper
from bs4 import BeautifulSoup

# --- Percorsi ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PRICES_FILE = DATA_DIR / "managers_prices.json"
HISTORY_FILE = DATA_DIR / "managers_history.json"

BASE_URL = "https://www.futbin.com"
MANAGER_PAGE = f"{BASE_URL}/27/manager-prices"
PRICE_ENDPOINT = f"{BASE_URL}/27/getPricesById"
HISTORY_ENDPOINT = f"{BASE_URL}/27/playerGraph"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_scraper():
    return cloudscraper.create_scraper()

def scarica(scraper, url, params=None, is_json=False):
    try:
        r = scraper.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code == 200:
            return r.json() if is_json else r.text
        print(f"  HTTP {r.status_code} per {url}")
    except Exception as e:
        print(f"  Errore: {e}")
    return None

def estrai_id_manager(html):
    soup = BeautifulSoup(html, "html.parser")
    ids = set()
    for attr in ["data-player-resource", "data-baseid", "data-id"]:
        for tag in soup.find_all(attrs={attr: True}):
            v = tag.get(attr)
            if v and str(v).isdigit():
                ids.add(str(v))
    for link in soup.find_all("a", href=True):
        m = re.search(r"/manager/(\d+)", link["href"])
        if m:
            ids.add(m.group(1))
    return sorted(ids, key=int)

def get_prezzo_corrente(scraper, mid):
    data = scarica(scraper, PRICE_ENDPOINT, params={"id": mid}, is_json=True)
    if not data:
        return None
    prices = data.get("total_prices", {})
    if not prices:
        for v in data.values():
            if isinstance(v, dict) and any(k in v for k in ("ps", "pc", "xbox")):
                prices = v
                break
    return {
        "id": mid,
        "ps": prices.get("ps"),
        "pc": prices.get("pc"),
        "xbox": prices.get("xbox"),
        "timestamp": datetime.utcnow().isoformat(),
    }

def get_storico_prezzi(scraper, mid):
    params = {
        "type": "daily_graph",
        "year": "27",
        "player": mid,
    }
    data = scarica(scraper, HISTORY_ENDPOINT, params=params, is_json=True)
    if not data:
        return {}
    history = {}
    for platform in ("ps", "pc", "xbox"):
        if platform in data:
            history[platform] = [
                {"date": datetime.utcfromtimestamp(p[0] / 1000).strftime("%Y-%m-%d"),
                 "price": p[1]}
                for p in data[platform]
            ]
    return history

def main():
    print("🚀 Avvio scraping allenatori...")
    scraper = get_scraper()

    html = scarica(scraper, MANAGER_PAGE)
    if not html:
        print("❌ Impossibile scaricare la pagina.")
        return

    ids = estrai_id_manager(html)
    print(f"✅ Trovati {len(ids)} ID")

    prices = []
    history = {}
    for i, mid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] ID {mid}...", end=" ", flush=True)
        p = get_prezzo_corrente(scraper, mid)
        if p:
            prices.append(p)
            print(f"PS={p['ps']} PC={p['pc']}")
        else:
            print("nessun prezzo")

        h = get_storico_prezzi(scraper, mid)
        if h:
            history[mid] = h

        time.sleep(1.5 + random.uniform(0, 0.5))

    PRICES_FILE.write_text(json.dumps(prices, indent=2, ensure_ascii=False))
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    print(f"💾 Salvati {len(prices)} prezzi e {len(history)} storici.")

if __name__ == "__main__":
    main()