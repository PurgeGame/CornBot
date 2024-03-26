import discord
from discord.ext import tasks
import requests
import os
import json
import math
from prettytable import PrettyTable
import aiohttp
import random
from dotenv import load_dotenv

load_dotenv()


GECKO_API = os.environ.get("GECKO_API")

intents = discord.Intents.default()  # Create a new Intents object with default settings
bot = discord.Bot(intents=intents)  # Pass the Intents object to the Bot

token = os.environ.get("DISCORD_BOT_SECRET")
global change_btc
change_btc = None



async def get_prices(coins):
    # Convert the list of coins to a comma-separated string
    coins_str = ','.join(coins)

    # Define the URL and headers
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coins_str}"
    headers = {"x-cg-demo-api-key": GECKO_API}

    # Send a request to the CoinGecko API
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

    # Check if the request was successful
    if response.status == 200:
        # Convert the list to a dictionary
        prices = {coin['id']: coin for coin in data}

        # Return the prices
        return prices
    else:
        # If the request was not successful, return an empty dictionary
        return {}
    
def round_sig(x, sigdig=2):
    """Round x to sigdig significant digits"""
    if x == 0: return 0   # can't log10(0)
    # n = digits left of decimal, can be negative
    n = math.floor(math.log10(abs(x))) + 1
    return round(x, sigdig - n)

    
async def check_coin(coin):
    coin = coin.lower()
    matching_ids = []
    with open('coins.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for line in data:
        if line['symbol'].lower() == coin or line['name'].lower() == coin or line['id'].lower() == coin:
            matching_ids.append(line['id'])
    if matching_ids:
        if len(matching_ids) == 1:
            return matching_ids[0]
        else:
            return await get_coin_with_lowest_market_cap_rank(matching_ids)
    else: 
        return False

async def get_coin_with_lowest_market_cap_rank(coin_ids):
    async with aiohttp.ClientSession() as session:
        lowest_rank_id = None
        lowest_rank = float('inf')
        for coin_id in coin_ids:
            async with session.get(f'https://api.coingecko.com/api/v3/coins/{coin_id}') as response:
                coin_data = await response.json()
                if 'market_cap_rank' in coin_data and coin_data['market_cap_rank'] is not None:
                    if coin_data['market_cap_rank'] < lowest_rank:
                        lowest_rank = coin_data['market_cap_rank']
                        lowest_rank_id = coin_id
        return lowest_rank_id

    
def format(price):
    if price > 100:
        price = f'{int(price):,}' 
    elif price > 1:
        price = round(price,2)
    else:
        price = round_sig(price,2)
    return price

@bot.slash_command(name="price", description="Show the current price for a coin")
async def price(ctx, coin: str):
    # Defer the response
    await ctx.defer()

    # Check the coin
    coin_id = await check_coin(coin)
    if not coin_id:
        # If the coin is not valid, send an error message
        await ctx.edit(content=f"Could not find a coin with the ID '{coin}'")
        return

    # Fetch the current price for the coin
    data = await get_prices([coin_id])

    if data and coin_id in data:
        price_data = data[coin_id]
        price = price_data['current_price']
        change = round(price_data['price_change_percentage_24h'],1)
        cap = int(price_data['market_cap'])
        ath = price_data['ath']
        ath_percentage = int(price_data['ath_change_percentage'])
        price = format(price)
        ath = format(ath)
        cap = format_number(cap)
        if change >= 20:
            await ctx.edit(content=f"The price of {coin_id} is ${price} (<a:STONKSgiga:963654243645022299> +{change}%). Market Cap: ${cap}. ATH: ${ath} ({ath_percentage}%)")
        elif change >= 10:
            await ctx.edit(content=f"The price of {coin_id} is ${price} (<:stonks:820769750896476181> +{change}%). Market Cap: ${cap}. ATH: ${ath} ({ath_percentage}%)")
        elif change >= 0:
            # Edit the response to send the actual content
            await ctx.edit(content=f"The price of {coin_id} is ${price} (⬈{change}%). Market Cap: ${cap}. ATH: ${ath} ({ath_percentage}%)")
        elif change > -10:
            # Edit the response to send the actual content
            await ctx.edit(content=f"The price of {coin_id} is ${price} (⬊{change}%). Market Cap: ${cap}. ATH: ${ath} ({ath_percentage}%)")
        else:
            await ctx.edit(content=f"The price of {coin_id} is ${price} (<:notstonks:820769947462402099> {change}%). Market Cap: ${cap}. ATH: ${ath} ({ath_percentage}%)")
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
        coin_id = await check_coin(coin)
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

def format_number(num):
    if num is None:
        return 'N/A'
    elif num >= 1e7:
        return f'{num/1e6:,.0f} M'
    elif num >= 1e3:
        return f'{round(num):,}'
    elif num < 0.01:
        return f'{num:.2e}'  # use scientific notation for very small numbers
    else:
        return f'{num:.2f}'

@bot.slash_command(name="search", description="Search for coins by name and display their IDs, price, and market cap")
async def search_coins(ctx, query: str):
    # Defer the response
    await ctx.defer()

    # Create an aiohttp.ClientSession
    async with aiohttp.ClientSession() as session:
        # Search for coins that match the query using the CoinGecko API
        async with session.get(f'https://api.coingecko.com/api/v3/search?query={query}') as response:
            matching_coins = await response.json()

    # Get the IDs of the top 10 matching coins
    matching_ids = [coin['id'] for coin in matching_coins['coins'][:10]]

    # Fetch the prices, market cap, 24-hour change, ath, and ath_change_percentage for the matching coins
    prices = await get_prices(matching_ids)

    # Create a table
    table = PrettyTable()
    table.field_names = ['ID', 'Price', 'Market Cap', 'Δ 24h', 'ATH', 'Δ ATH']
    table.align = 'r'  # right-align data
    table.align['ID'] = 'l'  # left-align IDs

    # Add a counter for the number of coins added to the table
    num_coins = 0

    for coin_id in matching_ids:
        if coin_id in prices:
            market_cap = prices[coin_id]['market_cap']
            if market_cap is not None:
                if market_cap < 1000000:
                    continue
            else:
                continue
            market_cap = format_number(market_cap)  

            price = format_number(prices[coin_id]['current_price']) if prices[coin_id]['current_price'] is not None else 'N/A'
            change = prices[coin_id]['price_change_percentage_24h']
            if change is not None:
                symbol = '+' if change >= 0 else '-'
                change = f"{symbol}{abs(change):.1f}"
            else:
                change = 'N/A'
            ath = format_number(prices[coin_id]['ath']) if prices[coin_id]['ath'] is not None else 'N/A'
            ath_change = prices[coin_id]['ath_change_percentage']
            ath_change = 'N/A' if ath_change is None else f'{ath_change:.0f}'
            table.add_row([coin_id, price, f'{market_cap}', f'{change}%', ath, f'{ath_change}%'])

            # Increment the counter
            num_coins += 1

    # Check if any coins were added to the table
    if num_coins == 0:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
    else:
        # Send the table
        await ctx.edit(content=f'```\n{table}\n```')

@bot.slash_command(name="id", description="Add a coin to your favorites by exact ID")
async def add_coin(ctx, coin_id: str):
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

    # Check if the coin_id exists in coins
    with open('coins.json', 'r') as f:
        coins = json.load(f)
    if any(coin['id'] == coin_id for coin in coins):
        # Add the coin to the favorites if it's not already there
        if coin_id not in favorites[user_id]:
            favorites[user_id].append(coin_id)

            # Save the updated favorites
            with open('favorites.json', 'w') as f:
                json.dump(favorites, f)

            # Edit the response to send the actual content
            await ctx.edit(content=f"Added coin to your favorites: {coin_id}")
        else:
            # Edit the response to send the actual content
            await ctx.edit(content="The coin you provided is already in your favorites.")
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="The coin you provided is not valid.")


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
        table.field_names = ["Coin", "Price", "Δ 24h", "Market Cap", "ATH", "Δ ATH"]
        table.align["Price"] = "r"
        table.align["Δ 24h"] = "r"
        table.align["Coin"] = "l"
        table.align["Market Cap"] = "r"
        table.align["ATH"] = "r"
        table.align["Δ ATH"] = "r"

        # Create a list of coins with their data
        coins_data = []
        for coin, data in prices.items():
            price = data['current_price']
            change = round(data['price_change_percentage_24h'],1)
            cap = int(data['market_cap'])
            ath = format(data['ath'])
            off_ath = int(data['ath_change_percentage'])
            if price > 100:
                price = f'{int(price):,}' 
            elif price > 1:
                price = round(price,2)
            else:
                price = round_sig(price,2)
            coins_data.append([coin, price, change, cap, ath, off_ath])

        # Sort the coins by market cap in descending order
        coins_data.sort(key=lambda x: x[3], reverse=True)

        # Add a row for each coin
        for coin_data in coins_data:
            table.add_row([coin_data[0], f"{coin_data[1]}", f"+{coin_data[2]}%" if coin_data[2] >= 0 else f"-{coin_data[2]}%", f"{format_number(coin_data[3])}", coin_data[4], f"{coin_data[5]}%"])

        # Edit the response to send the actual content
        await ctx.edit(content=f'```\n{table}\n```')
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
            coin_id = await check_coin(coin)
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
    rand = random.randint(0, 21)
    global change_btc
    try:
        if rand%3 == 1 or not change_btc:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
            headers = {"x-cg-demo-api-key": GECKO_API}
            response = requests.get(url, headers=headers)
            price_btc = response.json()['bitcoin']['usd']
            change_btc = int(response.json()['bitcoin']['usd_24h_change'] * 100)/100
        elif rand%3 == 0:
            response = requests.get('https://api.coindesk.com/v1/bpi/currentprice/BTC.json')
            price_btc = response.json()['bpi']['USD']['rate_float']
        else:
            response = requests.get('https://api.coinbase.com/v2/prices/BTC-USD/spot')
            price_btc = response.json()['data']['amount']
        price_btc = f'{int(float(price_btc)):,}'
        
    except:
        price_btc = .999
        change_btc = 0
    return (price_btc, change_btc)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

@tasks.loop(minutes = 1)  # Create a task that runs every minute
async def update_activity():

    price_btc, change = get_bitcoin_price()
    if price_btc == .999:
        return
    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬈{change}%"))
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬊{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} (:skull_crossbones: ⬊{change}% :skull_crossbones:)"))


bot.run(token)


