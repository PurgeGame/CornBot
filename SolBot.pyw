import discord
from discord.ext import tasks
import aiohttp
import os
import random
from dotenv import load_dotenv
from utils import format_price_display

load_dotenv()


intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

GECKO_API = os.environ.get("GECKO_API")
global change_eth
change_eth = None
global ratio


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

async def get_eth_price():
    rand = random.randint(0, 100)
    global change_eth
    global ratio
    try:
        async with aiohttp.ClientSession() as session:
            if rand%2 == 1 or change_eth is None:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=solana,ethereum&vs_currencies=usd&include_24hr_change=true"
                async with session.get(url) as response:
                    data = await response.json()
                price_eth = data['solana']['usd']
                price_btc = data['ethereum']['usd']
                change_eth = int(data['solana']['usd_24h_change'] * 100)/100
                ratio = price_eth/price_btc
            if rand%2 == 0:
                async with session.get('https://api.coinbase.com/v2/prices/SOL-USD/spot') as response:
                    data = await response.json()
                price_eth = data['data']['amount']
        price_eth = f'{int(float(price_eth)):,}'
        
    except:
        price_eth = .999
        change_eth = 0
        ratio = 0
    return (price_eth, change_eth, ratio)

@tasks.loop(minutes=1)  # Create a task that runs every minute
async def update_activity():

    price_eth, change_eth, ratio = await get_eth_price()
    if price_eth == .999:
        return
    price_display = format_price_display(price_eth, decimals=0)
    if change_eth >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_display} ⬈{abs(change_eth):.1f}% 🍹{f'{ratio:.4f}'[1:]}"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_display} ⬊{abs(change_eth):.1f}% 🍹{f'{ratio:.4f}'[1:]}"))

token = os.environ.get("SOL_BOT_SECRET")
bot.run(token)
