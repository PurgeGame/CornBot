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

@bot.slash_command(name="price", description="Show the current price for a coin")
async def price(ctx, coins: str):
    # Defer the response
    await ctx.defer()

    # Split the coins parameter by commas to get a list of coins
    coins = [coin.strip() for coin in coins.split(',')]

    # Create a list to store the messages
    messages = []

    # Loop over the list of coins
    for coin in coins:
        # Check the coin
        coin_id = await check_coin(coin)
        if not coin_id:
            # If the coin is not valid, add an error message to the list
            messages.append(f"Could not find a coin with the ID '{coin}'")
            continue

        # Fetch the current price for the coin
        data = await get_prices([coin_id])

        if data and coin_id in data:
            price_data = data[coin_id]
            price = price_data['current_price']
            change = round(price_data['price_change_percentage_24h'],1)
            cap = int(price_data['market_cap'])
            if cap == 0: 
                if 'fully_diluted_valuation' in data and data['fully_diluted_valuation'] is not None:
                    cap = int(data['fully_diluted_valuation'])
                else:
                    cap = '0'
            mc_rank = price_data['market_cap_rank']
            if mc_rank is None:
                mc_rank = 'N/A'
            ath = price_data['ath']
            ath_percentage = int(price_data['ath_change_percentage'])
            price = format_number(price)
            ath = format_number(ath)
            cap = format_number(cap)
            if change >= 20:
                messages.append(f"The price of {coin_id} is ${price} (<a:STONKSgiga:963654243645022299> +{change}%). Market Cap: ${cap} (#{mc_rank}). ATH: ${ath} ({ath_percentage}%)")
            elif change >= 10:
                messages.append(f"The price of {coin_id} is ${price} (<:stonks:820769750896476181> +{change}%). Market Cap: ${cap} (#{mc_rank}). ATH: ${ath} ({ath_percentage}%)")
            elif change >= 0:
                messages.append(f"The price of {coin_id} is ${price} (⬈{change}%). Market Cap: ${cap} (#{mc_rank}). ATH: ${ath} ({ath_percentage}%)")
            elif change > -10:
                messages.append(f"The price of {coin_id} is ${price} (⬊{change}%). Market Cap: ${cap} (#{mc_rank}). ATH: ${ath} ({ath_percentage}%)")
            else:
                messages.append(f"The price of {coin_id} is ${price} (<:notstonks:820769947462402099> {change}%). Market Cap: ${cap} (#{mc_rank}). ATH: ${ath} ({ath_percentage}%)")
        else:
            messages.append(f"Could not find a coin with the ID '{coin}'")

    # Join the messages into a single string and edit the response to send the actual content
    await ctx.edit(content='\n'.join(messages))



def is_number(n):
    try:
        float(n)
        return True
    except ValueError:
        return False

def round_sig(n, sig=2):
    return round(n, sig - int(floor(log10(abs(n)))) - 1)

def format_number(num):
    if num is None or not is_number(num):
        return 0
    else:
        num = float(num)
        if num >= 1e7:
            return f'{num/1e6:,.0f} M'
        elif num >= 1e3:
            return f'{int(num):,}'
        elif num == 0:
            return 0
        elif num < 0.01:
            return f'{num:.2e}'  # use scientific notation for very small numbers
        elif num > 1:
            return round(num, 2)
        elif num > .01:
            return f'{num:.2f}'
        else:
            return round_sig(num, 2)
        

async def display_coins(ctx, coins_data, display_id=False):
    # Create a table
    table = PrettyTable()
    table.field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'Market Cap', 'ATH', 'Δ ATH']
    table.align = 'r'  # right-align data
    table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs

    # Add a counter for the number of coins added to the table
    num_coins = 0

    for coin_id, coin_data in coins_data.items():
        prices = coin_data
        market_cap = prices['market_cap']
        if market_cap is not None:
            if market_cap < 1000000:
                continue
        else:
            continue
        market_cap = format_number(market_cap)  

        price = format_number(prices['current_price']) if prices['current_price'] is not None else 'N/A'
        change = prices['price_change_percentage_24h']
        if change is not None:
            symbol = '+' if change >= 0 else '-'
            change = f"{symbol}{abs(change):.1f}"
        else:
            change = 'N/A'
        ath = format_number(prices['ath']) if prices['ath'] is not None else 'N/A'
        ath_change = prices['ath_change_percentage']
        ath_change = 'N/A' if ath_change is None else f'{ath_change:.0f}'
        table.add_row([coin_id, price, f'{change}%', f'{market_cap}', ath, f'{ath_change}%'])

        # Increment the counter
        num_coins += 1

    # Check if any coins were added to the table
    if num_coins == 0:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
    else:
        # Send the table
        await ctx.edit(content=f'```\n{table}\n```')

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

        # Display the coins
        await display_coins(ctx, prices)
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="You don't have any favorite coins saved.")

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

    # Display the coins
    await display_coins(ctx, prices, display_id=True)

async def get_bitcoin_price():
    rand = random.randint(0, 21)
    global change_btc
    try:
        async with aiohttp.ClientSession() as session:
            if rand%3 == 1 or not change_btc:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
                headers = {"x-cg-demo-api-key": GECKO_API}
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    price_btc = data['bitcoin']['usd']
                    change_btc = int(data['bitcoin']['usd_24h_change'] * 100)/100
            elif rand%3 == 0:
                async with session.get('https://api.coindesk.com/v1/bpi/currentprice/BTC.json') as response:
                    data = await response.json()
                    price_btc = data['bpi']['USD']['rate_float']
            else:
                async with session.get('https://api.coinbase.com/v2/prices/BTC-USD/spot') as response:
                    data = await response.json()
                    price_btc = data['data']['amount']
            price_btc = f'{int(float(price_btc)):,}'
        
    except:
        price_btc = .999
        change_btc = 0
    return (price_btc, change_btc)

async def load_favorites():
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            return json.load(f)
    else:
        return {}

async def save_favorites(favorites):
    with open('favorites.json', 'w') as f:
        json.dump(favorites, f)

async def manage_coins(ctx, user_id, coins, action):
    favorites = await load_favorites()
    user_favorites = favorites.get(user_id, [])
    coin_ids = [await check_coin(coin) for coin in coins]
    if action == 'add':
        added_coins = [coin for coin in coin_ids if coin and coin not in user_favorites]
        user_favorites.extend(added_coins)
        message = f"Added coins to your favorites: {', '.join(added_coins)}"
    elif action == 'remove':
        removed_coins = [coin for coin in coin_ids if coin and coin in user_favorites]
        user_favorites = [coin for coin in user_favorites if coin not in removed_coins]
        message = f"Removed coins from your favorites: {', '.join(removed_coins)}"
    favorites[user_id] = user_favorites
    await save_favorites(favorites)
    return message

@bot.slash_command(name="add", description="Add coins to your favorites")
async def add(ctx, coins: str):
    await ctx.defer()
    coins = [coin.strip() for coin in coins.split(',')]
    message = await manage_coins(ctx, str(ctx.author.id), coins, 'add')
    await ctx.edit(content=message)

@bot.slash_command(name="remove", description="Remove coins from your favorites")
async def remove(ctx, coins: str):
    await ctx.defer()
    coins = [coin.strip() for coin in coins.split(',')]
    message = await manage_coins(ctx, str(ctx.author.id), coins, 'remove')
    await ctx.edit(content=message)

@bot.slash_command(name="addlist", description="Add a coin to the list")
async def addlist(ctx, list_name: str, coin: str):
    await ctx.defer()
    message = await manage_coins(ctx, list_name, [coin], 'add')
    await ctx.edit(content=message)

@bot.slash_command(name="removelist", description="Remove a coin from a list")
async def removefromlist(ctx, list_name: str, coin: str):
    await ctx.defer()
    message = await manage_coins(ctx, list_name, [coin], 'remove')
    await ctx.edit(content=message)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

@tasks.loop(minutes = 1)  # Create a task that runs every minute
async def update_activity():

    price_btc, change = await get_bitcoin_price()
    if price_btc == .999:
        return
    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬈{change}%"))
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬊{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} (:skull_crossbones: ⬊{change}% :skull_crossbones:)"))


bot.run(token)


