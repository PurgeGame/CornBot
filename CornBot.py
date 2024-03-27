import discord
from discord.ext import tasks
import os
import json
import math
from prettytable import PrettyTable
import aiohttp
import random
from dotenv import load_dotenv
from typing import Optional
import asyncio


load_dotenv()

token = os.environ.get("DISCORD_BOT_SECRET")
GECKO_API = os.environ.get("GECKO_API")
intents = discord.Intents.default() 
bot = discord.Bot(intents=intents)  
global change_btc
change_btc = None

async def fetch_data_from_api(url):
    headers = {"x-cg-demo-api-key": GECKO_API}
    # Send a request to the CoinGecko API
    async with aiohttp.ClientSession() as session:
        for i in range(2):  # Try twice
            if i == 0:
                async with session.get(url) as response:  # First try without headers
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        await asyncio.sleep(5)  # Wait for 5 seconds before the next try
            else:
                async with session.get(url, headers=headers) as response:  # Second try with headers
                    if response.status == 200:
                        data = await response.json()
                        return data
    return {}

async def get_prices(coins):
    # Convert the list of coins to a comma-separated string
    coins_str = ', '.join(coin for coin in coins if coin is not None)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coins_str}"
    data = await fetch_data_from_api(url)
    # Convert the list to a dictionary
    prices = {coin['id']: coin for coin in data}
    # Return the prices
    return prices

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
    # Convert the list of coin IDs to a comma-separated string
    coin_ids_str = ', '.join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_ids_str}"
    data = await fetch_data_from_api(url)
    # Find the coin with the lowest market cap rank
    lowest_rank_id = min(data, key=lambda coin: coin['market_cap_rank'] if coin['market_cap_rank'] is not None else float('inf'))['id']
    return lowest_rank_id


@bot.slash_command(name="price", description="Show the current price for a coin")
async def price(ctx, coins: str):
    await ctx.defer()
    # Split the coins parameter by commas to get a list of coins
    coins = [coin.strip() for coin in coins.split(',')]
    coins_data = {}
    for coin in coins:
        coin_id = await check_coin(coin)
        if not coin_id:
            continue
        data = await get_prices([coin_id])
        if data and coin_id in data:
            coins_data[coin_id] = data[coin_id]
    await display_coins(ctx, coins_data)

def is_number(n):
    try:
        float(n)
        return True
    except ValueError:
        return False

def round_sig(num, sig_figs):
    if num != 0:
        return round(num, -int(math.floor(math.log10(abs(num))) - (sig_figs - 1)))
    else:
        return 0  # Can't take the log of 0

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
            return f'{num:.2e}'
        elif num > 1:
            return round(num, 2)
        elif num > .01:
            return f'{num:.2f}'
        else:
            return round_sig(num, 2)
        
async def display_coins(ctx, coins_data, display_id=False, list_name=None):
    # Create a table
    table = PrettyTable()
    table.field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'Market Cap', 'Rank', 'ATH', 'Δ ATH']
    table.align = 'r' 
    table.align['ID' if display_id else 'Name'] = 'l' 
    # Filter coins with market cap >= 1 million
    filtered_coins = {coin_id: coin_data for coin_id, coin_data in coins_data.items()}# if coin_data['market_cap'] and coin_data['market_cap'] >= 1000000}

    for coin_id, prices in filtered_coins.items():
        market_cap = format_number(prices['market_cap'])  
        price = format_number(prices['current_price']) if prices['current_price'] else 'N/A'
        change = f"{'+-'[prices['price_change_percentage_24h'] < 0]}{abs(prices['price_change_percentage_24h']):.1f}" if prices['price_change_percentage_24h'] else 'N/A'
        ath = format_number(prices['ath']) if prices['ath'] else 'N/A'
        ath_change = prices['ath_change_percentage'] if prices['ath_change_percentage'] else 'N/A'
        mc_rank = prices['market_cap_rank'] if prices['market_cap_rank'] else 'N/A'
        table.add_row([coin_id, price, f'{change}%', f'{market_cap}', mc_rank, ath, f"{ath_change:02.0f}%"])
        
    # Check if any coins were added to the table
    if not filtered_coins:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
    else:
        # Send the table
        message = f'```\n{table}\n```'
        if list_name:
            message = f"Displaying coins from the list '{list_name}':\n" + message
        await ctx.edit(content=message)

@bot.slash_command(name="coins", description="Show current prices for your favorite coins")
async def coins(ctx, list_name: Optional[str] = None):
    await ctx.defer()
    user_id = str(ctx.author.id)
    favorites = {}
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            favorites = json.load(f)
    if list_name:
        if list_name in favorites:
            coins = favorites[list_name]
        else:
            await ctx.edit(content=f"The list '{list_name}' does not exist.")
            return
    elif user_id in favorites and favorites[user_id]:
        # Use the user's favorite coins if no list was provided
        coins = favorites[user_id]
    else:
        await ctx.edit(content="You don't have any favorite coins saved.")
        return
    prices = await get_prices(coins)
    await display_coins(ctx, prices, list_name=list_name)

@bot.slash_command(name="search", description="Search for coins by name and display their IDs, price, and market cap")
async def search_coins(ctx, query: str, limit: Optional[int] = 10):
    if limit > 50:
        limit = 50
    # Defer the response
    await ctx.defer()
    url = f'https://api.coingecko.com/api/v3/search?query={query}'
    matching_coins = await fetch_data_from_api(url)
    # Get the IDs of the top 10 matching coins
    matching_ids = [coin['id'] for coin in matching_coins['coins'][:limit]]
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
                data = await fetch_data_from_api(url)
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

    if action == 'add':
        added_coins = [coin for coin in coins if coin not in user_favorites]
        user_favorites.extend(added_coins)
        message = f"Added coins to your favorites: {', '.join(coin for coin in added_coins if coin is not None)}"
    elif action == 'remove':
        removed_coins = [coin for coin in coins if coin in user_favorites]
        user_favorites = [coin for coin in user_favorites if coin not in removed_coins]
        message = f"Removed coins from your favorites: {', '.join(removed_coins)}"

    if user_favorites:  # if the list is not empty
        favorites[user_id] = user_favorites
    else:  # if the list is empty
        del favorites[user_id]  # remove the key-value pair from the dictionary

    await save_favorites(favorites)
    return message

async def manage_coins_command(ctx, coins: str, user_id: str, action: str, list_name=None):
    await ctx.defer(ephemeral=True)
    coins = [coin.strip() for coin in coins.split(',')]
    coins = [await check_coin(coin) for coin in coins]
    message = await manage_coins(ctx, user_id, coins, action)
    if list_name:
        message = message.replace("Added coins to your favorites", "Added coins").replace("Removed coins from your favorites", "Removed coins")
        message += f" to the list {list_name}" if action == 'add' else f" from the list {list_name}"
    await ctx.edit(content=message)

async def check_list_name(list_name):
    return sum(c.isdigit() for c in list_name) <= 10

@bot.slash_command(name="add", description="Add coins to your favorites or a list")
async def add(ctx, coins: str, list_name: str = None):
    if list_name:
        if not await check_list_name(list_name):
            await ctx.send("List name cannot contain more than 10 digits.")
            return
        await manage_coins_command(ctx, coins, list_name, 'add', list_name)
    else:
        await manage_coins_command(ctx, coins, str(ctx.author.id), 'add')

@bot.slash_command(name="remove", description="Remove coins from your favorites or a list")
async def remove(ctx, coins: str, list_name: str = None):
    if list_name:
        if not await check_list_name(list_name):
            await ctx.send("List name cannot contain more than 10 digits.")
            return
        await manage_coins_command(ctx, coins, list_name, 'remove', list_name)
    else:
        await manage_coins_command(ctx, coins, str(ctx.author.id), 'remove')

@bot.slash_command(name="id", description="Add a coin to your favorites by exact ID")
async def add_coin(ctx, coin_id: str):
    # Defer the response
    await ctx.defer()

    user_id = str(ctx.author.id)

    # Check if the coin_id exists in coins
    with open('coins.json', 'r', encoding='utf-8') as f:
        coins = json.load(f)
    if any(coin['id'] == coin_id for coin in coins):
        # Add the coin to the favorites if it's not already there
        message = await manage_coins(ctx, user_id, [coin_id], 'add')

        # Edit the response to send the actual content
        await ctx.edit(content=message)
    else:
        # Edit the response to send the actual content
        await ctx.edit(content="The coin you provided is not valid.")

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


