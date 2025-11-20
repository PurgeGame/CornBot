import aiohttp
import asyncio
import json
import os
from dotenv import load_dotenv
import yfinance as yf  # Add yfinance for S&P 500 futures
from datetime import datetime, timedelta
import pandas as pd

load_dotenv()

async def fetch_primary_data(session):
    """Fetch data from CoinGecko (primary source) and Yahoo Finance for S&P 500 futures."""
    try:
        # Load API key from .env
        api_key = os.getenv("GECKO_API")
        if not api_key:
            raise Exception("CoinGecko API key not found in .env file.")

        # Fetch crypto data from CoinGecko with API key
        url = f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,pax-gold&vs_currencies=usd&include_24hr_change=true&x_cg_demo_api_key={api_key}"
        async with session.get(url) as response:
            if response.status == 429:  # Rate limit error
                print("Rate limited by CoinGecko. Waiting before retrying...")
                await asyncio.sleep(60)  # Wait for 60 seconds before retrying
                return await fetch_primary_data(session)  # Retry the request
            elif response.status != 200:
                raise Exception(f"Unexpected status code: {response.status}")
            price_data = await response.json()
        return price_data
    except Exception as e:
        print(f"Primary fetch failed: {e}")
        return None
    
async def update_data():
    async with aiohttp.ClientSession() as session:
        while True:
            data = await fetch_primary_data(session)
            if data:
                with open("crypto_data.json", "w") as f:
                    json.dump(data, f)
            else:
                print("Both primary and backup data fetches failed. No update performed.")
            await asyncio.sleep(60)  # Update every minute
if __name__ == "__main__":
    asyncio.run(update_data())