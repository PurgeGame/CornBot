import aiohttp
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def fetch_primary_data(session):
    """Fetch data from CoinGecko (primary source)."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,pax-gold&vs_currencies=usd&include_24hr_change=true"
        async with session.get(url) as response:
            price_data = await response.json()

        data = {
            "btc": {
                "price": f"{int(float(price_data['bitcoin']['usd'])):,}",
                "change": round(price_data['bitcoin']['usd_24h_change'], 1),
                "gold_ratio": price_data['bitcoin']['usd'] / price_data['pax-gold']['usd']
            },
            "eth": {
                "price": f"{int(float(price_data['ethereum']['usd'])):,}",
                "change": round(price_data['ethereum']['usd_24h_change'], 1),
                "btc_ratio": price_data['ethereum']['usd'] / price_data['bitcoin']['usd']
            },
            "sol": {
                "price": f"{int(float(price_data['solana']['usd'])):,}",
                "change": round(price_data['solana']['usd_24h_change'], 1),
                "btc_ratio": price_data['solana']['usd'] / price_data['bitcoin']['usd']
            }
        }
        return data
    except Exception as e:
        print(f"Primary (CoinGecko) fetch failed: {e}")
        return None

async def fetch_backup_prices(session):
    """Fetch only prices from Coinbase as a backup."""
    backup_data = {}
    try:
        for coin, endpoint in [("btc", "BTC-USD"), ("eth", "ETH-USD"), ("sol", "SOL-USD")]:
            url = f"https://api.coinbase.com/v2/prices/{endpoint}/spot"
            async with session.get(url) as response:
                data = await response.json()
                backup_data[coin] = f"{int(float(data['data']['amount'])):,}"
        return backup_data
    except Exception as e:
        print(f"Backup (Coinbase) fetch failed: {e}")
        return None

async def fetch_crypto_data():
    async with aiohttp.ClientSession() as session:
        # Try primary source first
        primary_data = await fetch_primary_data(session)
        if primary_data:
            return primary_data

        # If primary fails, use backup prices and update existing JSON
        try:
            with open("crypto_data.json", "r") as f:
                current_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If no existing file or invalid JSON, use default structure
            current_data = {
                "btc": {"price": "0", "change": 0, "gold_ratio": 0},
                "eth": {"price": "0", "change": 0, "btc_ratio": 0},
                "sol": {"price": "0", "change": 0, "btc_ratio": 0}
            }

        # Fetch backup prices
        backup_prices = await fetch_backup_prices(session)
        if backup_prices:
            # Update only the prices, keep old change and ratios
            for coin in ["btc", "eth", "sol"]:
                current_data[coin]["price"] = backup_prices.get(coin, current_data[coin]["price"])
            return current_data

        # If both fail, return None to indicate failure
        return None

async def update_data():
    while True:
        data = await fetch_crypto_data()
        if data:
            with open("crypto_data.json", "w") as f:
                json.dump(data, f)
        else:
            print("Both primary and backup data fetches failed. No update performed.")
        await asyncio.sleep(60)  # Update every minute

if __name__ == "__main__":
    asyncio.run(update_data())