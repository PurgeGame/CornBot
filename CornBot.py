import discord
from discord.ext import tasks
import requests
import os
import json
import math
import asyncio
from prettytable import PrettyTable
import aiohttp

GECKO_API = os.environ.get("GECKO_API")

intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

async def get_prices(coins):
    # Convert the list of coins to a comma-separated string
    coins_str = ','.join(coins)

    # Define the URL and headers
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coins_str}&vs_currencies=usd&include_market_cap=true&include_24hr_change=true&precision=full"
    headers = {"x-cg-demo-api-key": GECKO_API}

    # Send a request to the CoinGecko API
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

    # Check if the request was successful
    if response.status == 200:
        # Return the prices
        return data
    else:
        # If the request was not successful, return an empty dictionary
        return {}
    
def round_sig(x, sigdig=2):
    """Round x to sigdig significant digits"""
    if x == 0: return 0   # can't log10(0)
    # n = digits left of decimal, can be negative
    n = math.floor(math.log10(abs(x))) + 1
    return round(x, sigdig - n)

def check_coin(coin):
    coin = coin.lower()
    with open('coins.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for line in data:
        if line['symbol'] == coin or line['name']== coin:
             return line['id']
        if line['id'] == coin:
            return coin
    else:
        return False

@bot.slash_command(name="price", description="Show the current price for a coin")
async def price(ctx, coin: str):
    # Defer the response
    await ctx.defer()

    # Check the coin
    coin_id = check_coin(coin)
    if not coin_id:
        # If the coin is not valid, send an error message
        await ctx.edit(content=f"Could not find a coin with the ID '{coin}'")
        return

    # Fetch the current price for the coin
    data = await get_prices([coin_id])

    if data and coin_id in data:
        price_data = data[coin_id]
        price = price_data['usd']
        change = round(price_data['usd_24h_change'],1)
        cap = int(price_data['usd_market_cap'])
        if price > 100:
            price = int(price)
        elif price > 1:
            price = round(price,2)
        else:
            price = round_sig(price,2)
        if change >= 0:
            # Edit the response to send the actual content
            await ctx.edit(content=f"The price of {coin_id} is ${price} (↗{change}%). Market Cap: ${cap:,}")
        elif change > -10:
            # Edit the response to send the actual content
            await ctx.edit(content=f"The price of {coin_id} is ${price} (↘{change}%). Market Cap: ${cap:,}")
        else:
            await ctx.edit(content=f"The price of {coin_id} is ${price} (:skull_crossbones: ↘{change}% :skull_crossbones:). Market Cap: ${cap:,}")
    else:
        # Edit the response to send the actual content
        await ctx.edit(content=f"Could not find a coin with the ID '{coin}'")


@bot.slash_command(name="add", description="Add coins to your favorites")
async def add(ctx, coins: str):
    # Defer the response
    await ctx.defer()

    user_id = str(ctx.author.id)
    favorites = {}

    # Load the existing data if the file exists
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            favorites = json.load(f)

    # If the user has no favorites saved, create an empty list for them
    if user_id not in favorites:
        favorites[user_id] = []

    # Split the coins by comma and remove any whitespace
    coins = [coin.strip() for coin in coins.split(',')]

    # Add the coins to the favorites
    added_coins = []
    for coin in coins:
        coin_id = check_coin(coin)
        if coin_id and coin_id not in favorites[user_id]:
            favorites[user_id].append(coin_id)
            added_coins.append(coin)

    # Save the updated favorites
    with open('favorites.json', 'w') as f:
        json.dump(favorites, f)

    if added_coins:
        # Edit the response to send the actual content
        await ctx.edit(content=f"Added coins to your favorites: {', '.join(added_coins)}")
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="None of the coins you provided were added. They might already be in your favorites or they are not valid.")


@bot.slash_command(name="coins", description="Show current prices for your favorite coins")
async def coins(ctx):
    # Defer the response
    await ctx.defer()

    user_id = str(ctx.author.id)
    favorites = {}

    # Load the existing data if the file exists
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            favorites = json.load(f)

    # Check if the user has any favorites saved
    if user_id in favorites and favorites[user_id]:
        # Fetch the current prices for all favorite coins
        prices = await get_prices(favorites[user_id])

        # Create a table with headers
        table = PrettyTable()
        table.field_names = ["Coin", "Price", "24h Change", "Market Cap"]
        table.align["Price"] = "r"
        table.align["Coin"] = "l"
        table.align["Market Cap"] = "r"

        # Create a list of coins with their data
        coins_data = []
        for coin, data in prices.items():
            price = data['usd']
            change = round(data['usd_24h_change'],1)
            cap = int(data['usd_market_cap'])
            if price > 100:
                price = int(price)
            elif price > 1:
                price = round(price,2)
            else:
                price = round_sig(price,2)
            coins_data.append([coin, price, change, cap])

        # Sort the coins by market cap in descending order
        coins_data.sort(key=lambda x: x[3], reverse=True)

        # Add a row for each coin
        for coin_data in coins_data:
            table.add_row([coin_data[0], f"${coin_data[1]}", f"↗{coin_data[2]}%" if coin_data[2] >= 0 else f"↘{coin_data[2]}%", f"${coin_data[3]:,}"])

        # Edit the response to send the actual content
        await ctx.edit(content=f"```{table}```")
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="You don't have any favorite coins saved.")

@bot.slash_command(name="remove", description="Remove coins from your favorites")
async def remove(ctx, coins: str):
    # Defer the response
    await ctx.defer()

    user_id = str(ctx.author.id)
    favorites = {}

    # Load the existing data if the file exists
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            favorites = json.load(f)

    # Check if the user has any favorites saved
    if user_id in favorites:
        # Split the coins by comma and remove any whitespace
        coins = [coin.strip() for coin in coins.split(',')]

        # Remove the coins from the favorites
        removed_coins = []
        for coin in coins:
            coin_id = check_coin(coin)
            if coin_id and coin_id in favorites[user_id]:
                favorites[user_id].remove(coin_id)
                removed_coins.append(coin)

        # Save the updated favorites
        with open('favorites.json', 'w') as f:
            json.dump(favorites, f)

        if removed_coins:
            # Edit the response to send the actual content
            await ctx.edit(content=f"Removed coins from your favorites: {', '.join(removed_coins)}")
        else:
            # Edit the response to send the actual content
            await ctx.edit(content="None of the coins you provided were in your favorites or they are not valid.")
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="You don't have any favorite coins saved.")

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
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price} ↘{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price} (:skull_crossbones: ↘{change}% :skull_crossbones:)"))

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)
