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
                        await asyncio.sleep(2)  # Wait for 2 seconds before the next try
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
    table.align = 'r'  # right-align data
    table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs

    # Filter coins with market cap >= 1 million
    filtered_coins = {coin_id: coin_data for coin_id, coin_data in coins_data.items()}# if coin_data['market_cap'] and coin_data['market_cap'] >= 1000000}

    messages = []
    current_message = ''

    for coin_id, prices in filtered_coins.items():
        market_cap = format_number(prices['market_cap'])  
        price = format_number(prices['current_price']) if prices['current_price'] else 'N/A'
        change = f"{'+-'[prices['price_change_percentage_24h'] < 0]}{abs(prices['price_change_percentage_24h']):.1f}" if prices['price_change_percentage_24h'] else 'N/A'
        ath = format_number(prices['ath']) if prices['ath'] else 'N/A'
        ath_change = prices['ath_change_percentage'] if prices['ath_change_percentage'] else 'N/A'
        mc_rank = prices['market_cap_rank'] if prices['market_cap_rank'] else 'N/A'

        table.add_row([coin_id, price, f'{change}%', f'{market_cap}', mc_rank, ath, f"{ath_change:02.0f}%"])

        # Check if the table fits within the limit
        table_str = str(table)
        if len(table_str) > 2000:
            # If it doesn't fit, remove the last row and add the table to the messages
            table.del_row(-1)
            messages.append(current_message + f'```\n{table}\n```')
            # Create a new table with the row that didn't fit
            table = PrettyTable()
            table.field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'Market Cap', 'Rank', 'ATH', 'Δ ATH']
            table.align = 'r'  # right-align data
            table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs
            table.add_row([coin_id, price, f'{change}%', f'{market_cap}', mc_rank, ath, f"{ath_change:02.0f}%"])
            current_message = ''

    # Add the last table to the messages
    messages.append(current_message + f'```\n{table}\n```')

    # Check if any coins were added to the table
    if not filtered_coins:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
    else:
        # Send the tables
        if list_name:
            messages[0] = f"Displaying coins from the list '{list_name}':\n" + messages[0]

        await ctx.edit(content=messages[0])
        for message in messages[1:]:
            await ctx.send(content=message)

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
async def search_coins(ctx, query: str, num: Optional[int] = 10):
    await ctx.defer()
    url = f'https://api.coingecko.com/api/v3/search?query={query}'
    matching_coins = await fetch_data_from_api(url)
    matching_ids = [coin['id'] for coin in matching_coins['coins'][num]]
    prices = await get_prices(matching_ids)
    await display_coins(ctx, prices, display_id=True)

def get_emoji(action,coin):
    buy_emojis = ['<a:pepelaugh:922704567332917258> ', '<a:buybuybuy:920335813294841966> ', '<:dogeGIGA:839205306042286151> ']
    sell_emojis = ['<:harold:826533474886221904> ', '<:bonk:1056641594255736832>', '<:shrug:1203958281094299678>','<:cramer:1062188133711626301> ']
    bitcoin_emojis = [ '🌽', '<:SAYLOR:981349800110850048>','<:fink:1166095456774926456>']
    if action == 'BUY'  or action == 'LONG':
        # If the action is to buy, select a positive emoji
        if coin == 'bitcoin':
            return random.choice(bitcoin_emojis)
        else:
            return random.choice(buy_emojis)
    elif action == 'SHORT':
        # If the action is to sell, select a negative emoji
        return random.choice(sell_emojis)


@bot.slash_command(name="ofa", description="Suggests to buy or sell a random coin from your favorites or the default coins")
async def ofa(ctx):
    await ctx.defer()
    user_id = str(ctx.author.id)
    favorites = {}
    if os.path.exists('favorites.json'):
        with open('favorites.json', 'r') as f:
            favorites = json.load(f)
    coins = []
    if random.random() < .5:
        # Load every coin from anyone's favorites
        for user_favorites in favorites.values():
            coins += user_favorites
    else:
        if user_id in favorites and favorites[user_id]:
            # Use the user's favorite coins if they have any
            coins = favorites[user_id]
    # Add Bitcoin, Ethereum, and Solana if they are not already in the list
    for coin in ['bitcoin', 'ethereum', 'solana']:
        if coin not in coins:
            coins.append(coin)
    # Pick a random coin
    coin = random.choice(coins)
    # Get the price of the coin
    prices = await get_prices([coin])
    price = format_number(prices[coin]['current_price'])
    rand = random.random()
    if rand < .5:
        leverage = 0
    elif rand >.995:
        await ctx.edit(content=f'Official Financial Advice: Play Purge Game')
        return
    else:
        leverage = random.choice([6.9, 20, 42, 69, 100, 420])
    # Decide whether to buy or sell
    action = 'BUY' if random.random() < .7 and leverage == 0 else 'LONG' if random.random() < .7 and leverage > 0 else 'SHORT'
    emoji = get_emoji(action,coin)
    # Send the suggestion
    if leverage > 0:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, NOW at ${price}, with {leverage}x leverage. {emoji}')
    else:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, NOW at ${price}. {emoji}')

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


async def manage_coins(ctx, user_id, coins, action, list_name=None):
    favorites = await load_favorites()
    key = f'{list_name}_{ctx.guild.id}' if list_name else user_id  # use the server ID and list name as the key if a list name is provided
    user_favorites = favorites.get(key, [])
    if action == 'add':
        added_coins = [coin for coin in coins if coin not in user_favorites]
        user_favorites.extend(added_coins)
        message = f"Added coins to your favorites: {', '.join(coin for coin in added_coins if coin is not None)}"
    elif action == 'remove':
        removed_coins = [coin for coin in coins if coin in user_favorites]
        user_favorites = [coin for coin in user_favorites if coin not in removed_coins]
        message = f"Removed coins from your favorites: {', '.join(removed_coins)}"
    if user_favorites:  
        favorites[key] = user_favorites
    else:  
        if key in favorites:  # make sure the key exists before deleting it
            del favorites[key]  # remove the key-value pair from the dictionary
    await save_favorites(favorites)
    return message

async def manage_coins_command(ctx, coins: str, user_id: str, action: str, list_name=None):
    await ctx.defer(ephemeral=True)
    coins = [coin.strip() for coin in coins.split(',')]
    coins = [await check_coin(coin) for coin in coins]
    message = await manage_coins(ctx, user_id, coins, action, list_name)
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
    await ctx.defer()
    user_id = str(ctx.author.id)
    # Check if the coin_id exists in coins
    with open('coins.json', 'r', encoding='utf-8') as f:
        coins = json.load(f)
    if any(coin['id'] == coin_id for coin in coins):
        # Add the coin to the favorites if it's not already there
        message = await manage_coins(ctx, user_id, [coin_id], 'add')
        await ctx.edit(content=message)
    else:
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


