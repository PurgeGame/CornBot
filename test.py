import aiohttp
import os
from dotenv import load_dotenv
import asyncio
load_dotenv()
MAGIC_EDEN_API = os.getenv("MAGIC_EDEN_API")
import requests

url = "https://api-mainnet.magiceden.dev/v2/ord/btc/runes/collection_stats/search?window=1d&limit=2&sort=floorPrice&direction=desc"


headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}

response = requests.get(url, headers=headers)

print(response.text)