import discord
from discord.ext import commands, tasks
import requests
import os
import json

GECKO_API = os.environ.get("GECKO_API")


intents = discord.Intents.default()  # Create a new Intents object with default settings
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)  # Pass the Intents object to the Bot

def check_coin(coin):
    coin = coin.lower()
    with open('coins.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for line in data:
        if line['symbol'] == coin or line['name'] == coin:
            print(1)
        if line['symbol'] == coin:
             return line['id']
        if line['name']== coin:
            return coin
    else:
        return False


@bot.command()
async def price(ctx,coin: str):
    coin = check_coin(coin)
    if coin == False:
        await ctx.send(f"Could not find a coin with the ID '{coin}'")
    else:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_market_cap=true&include_24hr_change=true&precision=full"
        headers = {"x-cg-demo-api-key": GECKO_API}
        response = requests.get(url, headers=headers)
        data = response.json()

        if coin in data:
            price = data[coin]['usd']
            change = round(data[coin]['usd_24h_change'],1)
            cap = int(data[coin]['usd_market_cap'])
            if change >= 0:
                await ctx.send(f"The price of {coin} is ${int(price):,} (↗{change}%). Market Cap: ${cap:,}")
            else:
                await ctx.send(f"The price of {coin} is ${int(price):,} (↘{change}%). Market Cap: ${cap:,}")
        else:
            await ctx.send(f"Could not find a coin with the ID '{coin}'")

def get_bitcoin_price():
    global count
    global change
    count = 0

    response = requests.get('https://api.coindesk.com/v1/bpi/currentprice/BTC.json')
    price = response.json()['bpi']['USD']['rate_float']
    count += 1

    if count == 1:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
        headers = {"x-cg-demo-api-key": GECKO_API}
        response = requests.get(url, headers=headers)
        price = response.json()['bitcoin']['usd']
        change = int(response.json()['bitcoin']['usd_24h_change'] * 100)/100
    else:
        if count > 10:
            count = 0

    return (f'{int(price):,}' , change)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

@tasks.loop(minutes=1)  # Create a task that runs every minute
async def update_activity():
    price, change = get_bitcoin_price()
    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price} ↗{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price} ↘{change}%"))

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)