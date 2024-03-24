import discord
from discord.ext import tasks
import requests
import os
import random


intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

GECKO_API = os.environ.get("GECKO_API")
global change_eth
change_eth = None


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

def get_eth_price():
    rand = random.randint(0, 100)
    global change_eth
    try:
        if rand%2 == 1 or change_eth is None:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
            response = requests.get(url)
            price_eth = response.json()['ethereum']['usd']
            change_eth = int(response.json()['ethereum']['usd_24h_change'] * 100)/100
        if rand%2 == 0:
            response = requests.get('https://api.coinbase.com/v2/prices/ETH-USD/spot')
            price_eth = response.json()['data']['amount']
        price_eth = f'{int(float(price_eth)):,}'
        
    except:
        price_eth = .999
        change_eth = 0
    return (price_eth, change_eth)
@tasks.loop(minutes=1)  # Create a task that runs every minute
async def update_activity():

    price_eth, change_eth = get_eth_price()
    if price_eth == .999:
        return
    if change_eth >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_eth} ⬈{change_eth}%"))
    elif change_eth > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price_eth} ⬊{change_eth}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_eth} (:skull_crossbones: ⬊{change_eth}% :skull_crossbones:)"))

token = os.environ.get("ETH_BOT_SECRET")
bot.run(token)
