import discord
from discord.ext import tasks
import requests
import os


intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

if change_eth >= 0:
    await eth_bot.change_presence(activity=discord.Game(name=f"${price_eth} ↗{change_eth}%"))
elif change_eth > -10:
    await eth_bot.change_presence(activity=discord.Game(name=f"${price_eth} ↘{change_eth}%"))
else:
    await eth_bot.change_presence(activity=discord.Game(name=f"${price_eth} (:skull_crossbones: ↘{change_eth}% :skull_crossbones:)"))

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

def get_eth_price():
    global count
    count+=1
    if count%2 == 0:
        response = requests.get('https://api.coinbase.com/v2/prices/ETH-USD/spot')
        price = response.json()['data']['amount']
    else:
        response = requests.get('https://api.coindesk.com/v1/bpi/currentprice/ETH.json')
        price_eth = response.json()['bpi']['USD']['rate_float']
    if count > 20:
        count = 0

    return (f'{int(price_btc):,}' , change_btc,f'{int(price_eth):,}', change_eth)

@tasks.loop(minutes=1)  # Create a task that runs every minute
async def update_activity():
    price, change = get_eth_price()
    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price} ↗{change}%"))
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price} ↘{change}%"))

token = os.environ.get("ETH_BOT_SECRET")
bot.run(token)
