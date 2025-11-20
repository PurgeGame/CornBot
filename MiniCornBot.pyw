import discord
from discord.ext import tasks
import aiohttp
import os
import random
from dotenv import load_dotenv
from utils import format_number, format_price_display

load_dotenv()


intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

GECKO_API = os.environ.get("GECKO_API")
global change_btc
change_btc = None
global ratio


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready


async def get_btc_price():
    rand = random.randint(0, 100)
    global change_btc
    global btc_dominance
    try:
        async with aiohttp.ClientSession() as session:
            if rand%2 == 1 or change_btc is None:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
                async with session.get(url) as response:
                    data = await response.json()
                price_btc = data['bitcoin']['usd']
                change_btc = int(data['bitcoin']['usd_24h_change'] * 100)/100
                url = "https://api.coingecko.com/api/v3/global"
                async with session.get(url) as response:
                    data = await response.json()
                    btc_dominance = format_number(data["data"]["market_cap_percentage"]["btc"])
            if rand%2 == 0:
                async with session.get('https://api.coinbase.com/v2/prices/BTC-USD/spot') as response:
                    data = await response.json()
                price_btc = data['data']['amount']
        price_btc = f'{int(float(price_btc)):,}'
        
    except:
        price_btc = .999
        change_btc = 0
        btc_dominance = 0
    return (price_btc, change_btc,btc_dominance)

@tasks.loop(minutes=1)  # Create a task that runs every minute
async def update_activity():

    price_btc, change_btc, btc_dominance = await get_btc_price()
    if price_btc == .999:
        return
    price_display = format_price_display(price_btc, decimals=0)
    if change_btc >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_display} ⬈{abs(change_btc):.1f}% {btc_dominance}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_display} ⬊{abs(change_btc):.1f}% {btc_dominance}%"))

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)
