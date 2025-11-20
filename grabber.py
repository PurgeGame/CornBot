import aiohttp
import asyncio
import json
import os
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd

load_dotenv()

async def fetch_primary_data(session):
    """Fetch CoinGecko crypto + PAXG and S&P 500 futures (ES=F)."""
    try:
        api_key = os.getenv("GECKO_API")
        if not api_key:
            raise Exception("CoinGecko API key not found in .env file.")

        # Crypto + PAXG
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum,solana,pax-gold"
            "&vs_currencies=usd"
            "&include_24hr_change=true"
            f"&x_cg_demo_api_key={api_key}"
        )
        async with session.get(url) as response:
            if response.status == 429:
                print("Rate limited by CoinGecko. Sleeping 60s then retrying…")
                await asyncio.sleep(60)
                return await fetch_primary_data(session)
            if response.status != 200:
                raise Exception(f"CoinGecko status {response.status}")
            price_data = await response.json()

        # S&P 500 futures via yfinance
        loop = asyncio.get_running_loop()
        def _fetch_es():
            df = yf.Ticker("ES=F").history(period="2d", interval="1m")
            if df is None or df.empty:
                df = yf.Ticker("ES=F").history(period="5d", interval="5m")
            return df

        sp500_futures = await loop.run_in_executor(None, _fetch_es)
        if sp500_futures is None or sp500_futures.empty:
            raise Exception("Empty ES=F history")

        latest_price = float(sp500_futures["Close"].iloc[-1])
        latest_time = sp500_futures.index[-1]
        target_time = latest_time - pd.Timedelta(hours=24)
        price_24h_ago = sp500_futures["Close"].asof(target_time)
        if pd.isna(price_24h_ago):
            price_24h_ago = float(sp500_futures["Close"].iloc[0])
        sp500_change = ((latest_price - float(price_24h_ago)) / float(price_24h_ago)) * 100.0

        # Gold via PAXG
        gold_price = float(price_data["pax-gold"]["usd"])
        gold_change = round(float(price_data["pax-gold"]["usd_24h_change"]), 2)
        gold_sp500_ratio = gold_price / latest_price

        data = {
            "btc": {
                "price": f"{int(float(price_data['bitcoin']['usd'])):,}",
                "change": round(float(price_data["bitcoin"]["usd_24h_change"]), 2),
                "gold_ratio": float(price_data["bitcoin"]["usd"]) / gold_price,
            },
            "eth": {
                "price": f"{int(float(price_data['ethereum']['usd'])):,}",
                "change": round(float(price_data["ethereum"]["usd_24h_change"]), 2),
                "btc_ratio": float(price_data["ethereum"]["usd"]) / float(price_data["bitcoin"]["usd"]),
            },
            "sol": {
                "price": f"{float(price_data['solana']['usd']):,}",
                "change": round(float(price_data["solana"]["usd_24h_change"]), 2),
                "btc_ratio": float(price_data["solana"]["usd"]) / float(price_data["bitcoin"]["usd"]),
            },
            "sp500": {
                "price": f"{int(latest_price):,}",
                "change": round(sp500_change, 2),
            },
            "gold": {
                "price": f"{gold_price:,.2f}",
                "change": gold_change,
                "sp500_ratio": gold_sp500_ratio,
            },
        }
        return data
    except Exception as e:
        print(f"Primary fetch failed: {e}")
        return None

async def fetch_backup_prices(session):
    """Backup crypto prices from Coinbase. Ratios limited to crypto/BTC only."""
    try:
        prices = {}
        for coin, endpoint in [("btc", "BTC-USD"), ("eth", "ETH-USD"), ("sol", "SOL-USD")]:
            url = f"https://api.coinbase.com/v2/prices/{endpoint}/spot"
            async with session.get(url) as response:
                data = await response.json()
                prices[coin] = float(data["data"]["amount"])

        backup = {
            "btc": {"price": f"{int(prices['btc']):,}"},
            "eth": {"price": f"{int(prices['eth']):,}", "btc_ratio": prices["eth"] / prices["btc"]},
            "sol": {"price": f"{int(prices['sol']):,}", "btc_ratio": prices["sol"] / prices["btc"]},
        }
        return backup
    except Exception as e:
        print(f"Backup (Coinbase) fetch failed: {e}")
        return None

async def fetch_crypto_data(c):
    async with aiohttp.ClientSession() as session:
        # Try primary ~every 5th cycle to limit rate while staying fresh
        if c == 1:
            primary_data = await fetch_primary_data(session)
            if primary_data:
                return primary_data

        # Fallback: update only crypto prices, keep prior change/ratios and SPX/Gold as-is
        try:
            with open("crypto_data.json", "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            current_data = {
                "btc": {"price": "0", "change": 0, "gold_ratio": 0},
                "eth": {"price": "0", "change": 0, "btc_ratio": 0},
                "sol": {"price": "0", "change": 0, "btc_ratio": 0},
                "sp500": {"price": "0", "change": 0},
                "gold": {"price": "0", "change": 0, "sp500_ratio": 0},
            }

        # Ensure keys exist for upgrades
        current_data.setdefault("gold", {"price": "0", "change": 0, "sp500_ratio": 0})
        current_data.setdefault("sp500", {"price": "0", "change": 0})

        backup_prices = await fetch_backup_prices(session)
        if backup_prices:
            for coin in ["btc", "eth", "sol"]:
                if coin in backup_prices:
                    current_data[coin]["price"] = backup_prices[coin]["price"]
                    if "btc_ratio" in backup_prices[coin]:
                        current_data[coin]["btc_ratio"] = backup_prices[coin]["btc_ratio"]
            return current_data

        return None

async def update_data():
    c = 0
    while True:
        c = 1 if c >= 5 else c + 1
        data = await fetch_crypto_data(c)
        if data:
            try:
                with open("crypto_data.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except Exception as e:
                print(f"Write error: {e}")
        else:
            print("Both primary and backup fetches failed. No update.")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(update_data())
