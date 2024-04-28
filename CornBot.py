import discord
from discord.ext import tasks, commands
import os
import json
import math
from prettytable import PrettyTable
from zoneinfo import ZoneInfo
import aiohttp
import random
from dotenv import load_dotenv
from typing import Optional
import asyncio
import time
from datetime import datetime, timezone, timedelta
from utils import *
from ofa import *
from discord import File
import glob
import shutil
import matplotlib.pyplot as plt
load_dotenv()
coin_data = {}
runes_data = {}

def check_and_copy_files(file_paths, fallback_paths):
    for file_path, fallback_path in zip(file_paths, fallback_paths):
        if not os.path.exists(file_path):
            if os.path.exists(fallback_path):
                shutil.copy(fallback_path, file_path)
            else:
                print(f"Neither the file {file_path} nor the fallback {fallback_path} exists.")

# List of file paths and their corresponding fallback paths
file_paths = ['favorite_coins.json', 'alerts.json', 'favorite_runes.json']
fallback_paths = ['favorite_coins_fallback.json', 'alerts_fallback.json', 'favorite_runes_fallback.json']

check_and_copy_files(file_paths, fallback_paths)

def print_favorite_runes(user_id):
    # Load the favorite runes from the JSON file
    with open('favorite_runes.json', 'r') as f:
        favorites_runes = json.load(f)

    # Get the user's favorite runes
    user_runes_dict = favorites_runes.get(str(user_id), {'runes': {}})
    user_favorites_runes = user_runes_dict['runes']

    # Create a comma-separated string of the favorite runes
    favorite_runes_str = ','.join(user_favorites_runes)

    print(favorite_runes_str)

def load_most_recent_json():
    global coin_data
    global runes_data
    # Get a list of all JSON files in the 'historical' folder
    files = glob.glob('historical/*.json')

    # Sort the files by modification time
    files.sort(key=os.path.getmtime)

    # Get the most recent file
    most_recent_file = files[-1]

    # Load the data from the most recent file
    with open(most_recent_file, 'r') as f:
        data = json.load(f)
    coin_data = data.get('coin_data', {})
    runes_data = data.get('runes_data', {})
    return data

load_most_recent_json()

class CustomContext(commands.Context):
    async def send(self, content=None, **kwargs):
        server_id = str(self.guild.id)
        spam_channels = self.get_spam_channels()

        if self.should_force_all_messages(server_id, spam_channels):
            self.set_channel(spam_channels[server_id]['channel_id'])

        ephemeral = kwargs.pop('ephemeral', False)
        if ephemeral and isinstance(self, commands.InteractionContext):
            await self.followup.send(content, ephemeral=True, **kwargs)
        else:
            await super().send(content, **kwargs)

    async def defer(self, ephemeral=False):
        if ephemeral and isinstance(self, commands.InteractionContext):
            await super().defer(ephemeral=True)
        else:
            await super().defer()

    async def edit(self, **fields):
        await super().edit(**fields)

    def get_spam_channels(self):
        return load_json_file('spam_channels.json')

    def should_force_all_messages(self, server_id, spam_channels):
        return server_id in spam_channels and spam_channels[server_id]['force_all_messages']

    def set_channel(self, channel_id):
        self.channel = self.bot.get_channel(int(channel_id))
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents, context_class=CustomContext)

token = os.environ.get("DISCORD_BOT_SECRET")
GECKO_API = os.environ.get("GECKO_API")
MAGIC_EDEN_API = os.environ.get("MAGIC_EDEN_API")
global change_btc
change_btc = 0



def load_json_file(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return data

async def fetch_data_from_api(url):
    headers = {"x-cg-demo-api-key": GECKO_API}
    # Send a request to the CoinGecko API
    async with aiohttp.ClientSession() as session:
        for i in range(3):  # Try three times
            async with session.get(url, headers=(headers if i > 0 else None)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    if i < 2:  # Don't wait after the last try
                        await asyncio.sleep(2)  # Wait for 2 seconds before the next try
    return {}

def find_min_market_cap_rank(matching_ids):
    global coin_data  # Use the global variable

    # Filter coin_data to only include coins with an ID in matching_ids
    filtered_coin_data = {coin_id: data for coin_id, data in coin_data.items() if coin_id in matching_ids}

    # Find the coin with the minimum market cap rank
    min_market_cap_rank_coin = min(filtered_coin_data, key=lambda coin_id: filtered_coin_data[coin_id]['market_cap_rank'] if filtered_coin_data[coin_id]['market_cap_rank'] is not None else float('inf'))

    return min_market_cap_rank_coin

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
            data = await fetch_coin_data(matching_ids)
            return find_min_market_cap_rank(matching_ids)
    else: 
        return False
    
@bot.slash_command(name="graph", description="Generates a graph")
async def graph(ctx: commands.Context, rune: str, start: str = "2024-04-26T00:00:00", interval: str = "1m"):
    global runes_data
    await ctx.defer()
    price_list = runes_data[rune]['price_list']

    # Generate a list of timestamps for the x-axis
    timestamps = range(len(price_list))

    plt.plot(timestamps, price_list)

    plt.xlabel('Time (in minutes)')
    plt.ylabel('Price')
    plt.title(f'Price Graph for {rune['name']}')

    # Save the graph as an image file
    plt.savefig('graph.png')

    # Send the image file in Discord
    await ctx.send(file=File('graph.png'))


    
@bot.slash_command(name="price", description="Show the current price for a coin or rune")
async def price(ctx, items: str, include_historical: bool = False):
    global runes_data
    global coin_data
    await ctx.defer()
    # Split the items parameter by commas to get a list of items
    items = [item.strip() for item in items.split(',')]
    coins_data = {}
    rune_data = {}
    for item in items:
        if is_rune(item):
            rune_id = sanitize_rune(item)
            if rune_id:
                if rune_id in runes_data:
                    rune_data[rune_id] = runes_data[rune_id]
                else:
                    data = await parse_rune_data(rune_id)
                    if data:
                        rune_data[rune_id] = runes_data[rune_id]

        else:

            coin_id = await check_coin(item)

            if coin_id:
                if coin_id not in coin_data:
                    response = await fetch_coin_data([coin_id])
                    if response:
                        if coin_id in coin_data:
                            coins_data[coin_id] = coin_data[coin_id]
                else:
                    coins_data[coin_id] = coin_data[coin_id]
    if rune_data == {} and coins_data == {}:
        await ctx.edit(content="Item not found.")
        return

    if rune_data:
        await display_runes(ctx, rune_data)
    if coins_data:
        await display_coins(ctx, coins_data, include_historical = include_historical)

async def create_table_coins(coins_data, display_id, include_historical=False):
    if include_historical:
        field_names = ['ID' if display_id else 'Name', 'Price', 'M Cap', 'Δ 24h', 'Δ 7d', 'Δ 30d', 'Δ 1y', 'ΔATH']
    else:
        field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'M Cap', 'ΔATH']

    table = PrettyTable()
    table.field_names = field_names
    table.align = 'r'  # right-align data
    table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs

    for coin_id, coin_data in coins_data.items():  # renamed from prices to coin_data
        name = truncate_name(coin_data['name'],20)
        market_cap = format_number(coin_data['market_cap']) if format_number(coin_data['market_cap']) != 0 else 'N/A'
        price = format_number(coin_data['current_price'],bitcoin=True) if coin_data['current_price'] else 'N/A'
        change_24h = format_change(coin_data['change_24h']) if coin_data['change_24h'] else 'N/A'
        ath_change = format_change(coin_data['ath_change_percentage']) if coin_data['ath_change_percentage'] else 'N/A'
        if include_historical:
            change_7d = format_change(coin_data.get('change_7d'))
            change_30d = format_change(coin_data.get('change_30d'))
            change_1y = format_change(coin_data.get('change_1y'))
            row_data = [name if not display_id else coin_id, price, market_cap, change_24h, change_7d, change_30d, change_1y, ath_change]
        else:
            row_data = [name if not display_id else coin_id, price, change_24h, market_cap, ath_change]

        table.add_row(row_data)
    return table

async def create_table_runes(runes,user_id):
    global coin_data
    field_names = [ 'Name', 'Price', 'Δ 24h', 'M Cap', '24h VOL', 'Owned', 'Value']
    table = PrettyTable()
    table.field_names = field_names
    table.align = 'r'  # right-align data
    table.align['Name'] = 'l'  # left-align IDs
    table.align['Sym'] = 'l'  # left-align IDs

    total_value = 0
    rows = []  # Store the rows here first
    for coin_id, rune_data in runes.items():
        owned_runes = check_coin_quantity(user_id, coin_id)
        quantity_owned = float(owned_runes['balance']) if owned_runes is not None and 'balance' in owned_runes else 0
        unformatted_price = rune_data['current_price']

        symbol = rune_data['symbol'] if rune_data['symbol'] else ''
        name = truncate_name(rune_data['name'],20)
        market_cap = format_number(rune_data['market_cap']) if format_number(rune_data['market_cap']) != 0 else 'N/A'
        price = format_number(rune_data['current_price']) if rune_data['current_price'] else 'N/A'
        change_24h = format_change(rune_data['change_24h']) if rune_data['change_24h'] else 'N/A'
        sat_price = float(coin_data['bitcoin']['current_price']) / 100000000
        volume_24h = format_number(int(rune_data['volume_24h']) * sat_price) if rune_data['volume_24h'] else 'N/A'

        
        value = format_number_with_symbol(quantity_owned * unformatted_price * sat_price,'USD',True,bitcoin=True) if quantity_owned is not None and price != 'N/A' else 'N/A'
  
       
        if volume_24h == 'N/A' or rune_data['volume_24h'] < 1000000:
            volume_24h = 0
            price = 'N/A'
            market_cap = 'N/A'
            change_24h = 'N/A'
            value = 'N/A'
        if value != 'N/A':
            total_value += quantity_owned * unformatted_price * sat_price
        quantity_owned = format_number_with_symbol(quantity_owned,symbol) if quantity_owned is not None else '0'
        row_data = [name, price, change_24h, market_cap, volume_24h, quantity_owned, value]
        rows.append(row_data)  # Add the row data to the list

    # Sort the rows by value (assuming value is a float)
    rows.sort(key=lambda row: convert_to_float(row[-1].replace(',', '').replace('$', '')) if row[-1] != 'N/A' else 0, reverse=True)
    # Add the sorted rows to the table
    for row in rows:
        table.add_row(row)
    ath = False
    with open('favorite_runes.json', 'r+') as f:
        favorite_runes = json.load(f)
        if 'total_value' not in favorite_runes[user_id] or total_value > favorite_runes[user_id]['total_value']:
            favorite_runes[user_id]['total_value'] = total_value
            f.seek(0)  # Move the cursor to the beginning of the file
            json.dump(favorite_runes, f, indent=4)
            f.truncate()  # Remove any remaining content
            ath = True

    return table,total_value,ath

async def display_coins(ctx, coins_data, display_id=False, include_historical=False):
    filtered_coins = {coin_id: coin_data for coin_id, coin_data in coins_data.items()}

    if not filtered_coins:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
        return

    table = await create_table_coins(filtered_coins, display_id, include_historical)
    messages = await split_table(table)


    await ctx.edit(content=messages[0])
    for message in messages[1:]:
        await ctx.send(content=message)

async def display_runes(ctx, runes_data):
    table, total_value,ath = await create_table_runes(runes_data, str(ctx.author.id))
    messages = await split_table(table)
    total_value = format_number_with_symbol(total_value,'USD',True,bitcoin=True)
    await ctx.edit(content=messages[0])
    for message in messages[1:]:
        await ctx.send(content=message)

    # Send a message about the total value
    if ath:
        await ctx.send(content=f'Total portfolio value: {total_value}, a new ATH!')
    else:
        await ctx.send(content=f'Total portfolio value: {total_value}')
            
@bot.slash_command(name="coins", description="Show current prices for your favorite coins")
async def coins(ctx, include_historical: Optional[bool] = False):
    await ctx.defer()
    user_id = str(ctx.author.id)
    favorites = load_favorites()
    if user_id in favorites and favorites[user_id]:
        coins = favorites[user_id]
    else:
        await ctx.edit(content="You don't have any favorite coins saved.")
        return
    filtered_coins_data = {coin_id: coin_data[coin_id] for coin_id in coins if coin_id in coin_data}
    await display_coins(ctx, filtered_coins_data, include_historical=include_historical)

async def get_my_runes(address,rune):
    url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/wallet/balances/{address}/{rune}"
    headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200 and response.content_type == 'application/json':
                data = await response.json()
                return data
            else:
                return {}

@bot.slash_command(name="runes", description="Show your runes")
async def runes(ctx, update_quantity: Optional[bool] = False, address: Optional[str] = None,):
    global runes_data
    await ctx.defer()
    user_id = str(ctx.author.id)
    if address is None:
        if not os.path.exists('favorite_runes.json'):
            return None
        else:
            user_data = get_user_data(user_id)
            if user_data is None:
                await ctx.edit(content="User not found.")
                return None
            if 'address' in user_data:  # Check if the 'address' key exists in the user_data dictionary
                address = user_data['address']
    else:
        add_or_update_user_address(user_id, address)
    runes = load_user_runes(user_id)
    if update_quantity:
        if runes is None:
            await ctx.edit(content="You don't have any favorite runes saved.")
            return
        for rune in runes:
            rune_data = await get_my_runes(address,rune)
            if rune_data == {}:
                await ctx.edit(content=f"{rune} not found.")
                continue
            add_rune_data(user_id, rune_data)
    runes = load_user_runes(user_id)
    if runes is None:
        await ctx.edit(content="You don't have any favorite runes saved.")
        return
    else:
         await fetch_coin_data(runes)

    filtered_runes_data = {rune: runes_data[rune] for rune in runes if rune in runes_data}

    await display_runes(ctx, filtered_runes_data)

def add_rune_data(user_id, rune_data):
    # Load the existing data from the JSON file
    if not os.path.exists('favorite_runes.json'):
        return False

    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    # Check if the user exists
    if user_id not in user_data:
        return False

    # Initialize the 'runes' key if it doesn't exist
    if 'runes' not in user_data[user_id]:
        user_data[user_id]['runes'] = {}

    # Check if 'formattedBalance' is in rune_data
    if 'formattedBalance' not in rune_data:
        return False

    # Add the rune data to the user's data
    user_data[user_id]['runes'][rune_data['ticker']] = {
        'balance': rune_data['formattedBalance']
    }

    # Write the updated data back to the JSON file
    with open('favorite_runes.json', 'w') as f:
        json.dump(user_data, f, indent=4)

@bot.slash_command(name="search", description="Search for coins by name and display their IDs, price, and market cap")
async def search_coins(ctx, query: str, num: Optional[int] = 10):
    await ctx.defer()
    url = f'https://api.coingecko.com/api/v3/search?query={query}'
    matching_coins = await fetch_data_from_api(url)
    matching_ids = [coin['id'] for coin in matching_coins['coins'][:num]]
    
    if not matching_ids:
        await ctx.edit(content="No matching coins found.")
        return

    coin_data = await fetch_coin_data(matching_ids)
    await display_coins(ctx, coin_data, display_id=True)


@bot.slash_command(name="ofa", description="Gives Official Financial Advice")
async def ofa(ctx):
    await ctx.defer()
    global coin_data
    global runes_data
    user_id = str(ctx.author.id)
    #print_favorite_runes(user_id)
    leverage = get_leverage()
    action = get_action(leverage)
    
    if random.random() < 0.5:
        favorite_coins = load_favorites("coins")
        coins = get_coins(user_id, favorite_coins)
        coin = random.choice(coins)
        if coin in coin_data:  # Check if the key exists in the dictionary
            price = coin_data[coin]['current_price']
        else:
            await ctx.edit(content=f"add more coins bugged.")
            return
        name = coin_data[coin]['name']
        buy_time, buy_price = get_buy_time_and_price(coin_data, coin, price)  # renamed from prices to coin_data
        emoji = get_emoji(action,coin)
    else:
        favorite_runes = load_favorites("runes")
        runes = get_all_runes(favorite_runes)
        if runes:  # Check if the list is not empty
            rune = random.choice(runes)
        else:
            await ctx.edit(content="You don't have any favorite runes saved, add one so this doesn't break til I fix it")
            return          
        price = runes_data[rune]['current_price']
        name = runes_data[rune]['name']
        buy_time, buy_price = get_buy_time_and_price(runes_data, rune, price)
        emoji = get_emoji(action,rune)

    await send_advice(ctx, action, name, buy_time, buy_price, leverage, emoji)

def parse_data(data):
    
    global coin_data  # Use the global variable

    data = {coin['id']: coin for coin in data}

    for coin_id, coin in data.items():
        name = coin['name']  # Extract the name
        current_price = coin['current_price']
        ath = coin['ath']
        ath_date = parse_date(coin['ath_date'])
        market_cap = coin['market_cap']
        market_cap_rank = coin['market_cap_rank']
        change_1y = coin.get('price_change_percentage_1y_in_currency')
        change_24h = coin.get('price_change_percentage_24h')
        change_30d = coin.get('price_change_percentage_30d_in_currency')
        change_7d = coin.get('price_change_percentage_7d_in_currency')
        ath_change_percentage = coin.get('ath_change_percentage')

        # Update the coin data in parsed_data or add it if it doesn't exist
        coin_data[coin_id] = {
            'name': name,  # Add the name to the parsed data
            'current_price': current_price,
            'market_cap': market_cap,
            'number' : None,
            'ath': ath,
            'ath_date': ath_date,
            'market_cap_rank': market_cap_rank,
            'change_1y': change_1y,
            'change_24h': change_24h,
            'change_30d': change_30d,
            'change_7d': change_7d,
            'ath_change_percentage': ath_change_percentage,
            'volume_24h': None,
            }

    return coin_data

from datetime import datetime

async def parse_rune_data(rune_list):
    global runes_data  # Use the global variable
    global coin_data

    for rune in rune_list:
        new_data = await fetch_rune_data(rune)  # Assuming fetch_rune_data is a function that fetches data for a rune
        coin_id = new_data.get('rune', None)
        symbol = new_data.get('symbol', None)
        name = new_data.get('name', None)
        number = new_data.get('runeNumber', None)
        current_price = float(new_data.get('floorUnitPrice', {}).get('formatted', '0'))  # Convert from BTC to sats
        market_cap_in_btc = new_data.get('marketCap', 0)
        volume_24h = new_data.get('volume', {}).get('24h', 0)

        # Convert the market cap from Bitcoin to dollars
        btc_price_in_usd = coin_data['bitcoin']['current_price']
        market_cap_in_usd = market_cap_in_btc * btc_price_in_usd

        # Get the current time
        now = datetime.now()
    

        
        # If the coin data doesn't exist, initialize it with an empty list
        if coin_id not in runes_data or 'price_list' not in runes_data[coin_id]:
            runes_data[coin_id] = {'price_list': []}

        # If the price list has more than 24 items, remove the oldest one
        if 'price_list' in runes_data[coin_id] and len(runes_data[coin_id]['price_list']) >= 24*60:
            runes_data[coin_id]['price_list'].pop(0)

        # Add the current price to the price list
        if 'price_list' not in runes_data[coin_id]:
            runes_data[coin_id]['price_list'] = []

        runes_data[coin_id]['price_list'].append(current_price)

        # Calculate the percentage change in the current price versus the oldest data in the price list
        # Only when the price list has a full 24 hours of data
        if coin_id in runes_data and 'price_list' in runes_data[coin_id] and len(runes_data[coin_id]['price_list']) == 24*60:
            oldest_price = runes_data[coin_id]['price_list'][0]
            change_24h = ((current_price - oldest_price) / oldest_price) * 100
        else:
            change_24h = None
        ath_change_percentage = None
        if coin_id in runes_data:
            ath = runes_data[coin_id].get('ath', None)
            ath_date = parse_date(runes_data[coin_id].get('ath_date', None))
        else:
            ath_date = None
            ath = None
        now = now.strftime("%d-%m-%Y %H:%M")
        # Update the rune data in runes_data or add it if it doesn't exist
        if coin_id not in runes_data:
            runes_data[coin_id] = {}
            ath = current_price
            ath_date = now
        else:
            if runes_data[coin_id].get('ath') is None:
                ath = current_price
                ath_date = now
            else:
                if runes_data[coin_id]['ath'] != 0:
                    ath_change_percentage = ((current_price - runes_data[coin_id]['ath']) / runes_data[coin_id]['ath']) * 100
                else:
                    ath_change_percentage = None  # or some other value that makes sense in your context
                if current_price > runes_data[coin_id]['ath']:
                    ath = current_price
                    ath_date = now

        runes_data[coin_id].update({
            'name': name,
            'symbol': symbol,
            'number' : number,
            'current_price': current_price,
            'market_cap': market_cap_in_usd,
            'ath': ath,
            'ath_date': ath_date,
            'market_cap_rank': None,
            'change_1y': None,
            'change_24h': change_24h,
            'change_30d': None,
            'change_7d': None,
            'ath_change_percentage': ath_change_percentage,
            'volume_24h': volume_24h,
        })

    return runes_data

async def fetch_coin_data(coin_ids):
    global coin_data
    success = 0
    coin_id_str = ','.join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_id_str}&price_change_percentage=7d%2C30d%2C1y"
    raw_data_list = await fetch_data_from_api(url)
    if raw_data_list:
        for item in raw_data_list:
            if item.get('id') == 'bitcoin':
                success = True

        parse_data(raw_data_list)  # Update the coin_data dictionary with the parsed data
    return success



async def fetch_rune_data(rune_name):
    
    url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/market/{rune_name}/info"
    headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}

    async with aiohttp.ClientSession() as session:

        async with session.get(url, headers=headers) as response:
            if response.status == 200 and response.content_type == 'application/json':
                data = await response.json()
                
                if isinstance(data, dict) and 'rune' in data:
                    return data
                else:
                    return {}
            else:
                return {}
            
async def fetch_bitcoin_price_fallback():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.coindesk.com/v1/bpi/currentprice/BTC.json') as response:
                data_btc = await response.json()
                return {'current_price': int(data_btc['bpi']['USD']['rate_float'])}
        except:
            try:
                async with session.get('https://api.coinbase.com/v2/prices/BTC-USD/spot') as response:
                    data_btc = await response.json()
                    return {'current_price': int(float(data_btc['data']['amount']))}
            except:
                return {'current_price': .999}
            
async def get_coin_data(coins):
    global coin_data
    coingecko_success = True
    try:
        coingecko_success = await fetch_coin_data(coins)

    except:
        data = {}
        coingecko_success = False
    if not coingecko_success:
        btc_price = await fetch_bitcoin_price_fallback()
        if btc_price:
            coin_data['bitcoin']['current_price'] = btc_price['current_price']
    if coingecko_success and 'change_24h' in coin_data['bitcoin']:
        change_btc = coin_data['bitcoin']['change_24h']
    else:
        change_btc = 0
        print('Error fetching BTC data') 

    return (coin_data['bitcoin']['current_price'], change_btc, coingecko_success)

async def validate_rune(rune):
    if rune not in runes_data:
        if await fetch_rune_data(rune) == {}:
            return False
        else:
            return True
    else:
        return True
    
async def manage_coins(ctx, user_id, coins, action):
    favorites_coins = load_favorites('coins')
    favorites_runes = load_favorites('runes')
    key = user_id  # use the server and list name as the key if a list name is provided
    user_favorites_coins = favorites_coins.get(key, [])
    user_runes_dict = favorites_runes.get(key, {'runes': {}})
    user_favorites_runes = user_runes_dict['runes']
    added_coins = []
    added_runes = []
    removed_coins = []
    removed_runes = []
    if action == 'add':
        for coin in coins:
            if isinstance(coin, bool):
                continue  # Skip this iteration if coin is a boolean
            if is_rune(coin):
                if coin not in user_favorites_runes:
                    user_favorites_runes[coin] = {}  # Initialize the rune as a dictionary
                    added_runes.append(coin)
            else:
                if coin not in user_favorites_coins:
                    user_favorites_coins.append(coin)
                    added_coins.append(coin)
    elif action == 'remove':
        for coin in coins:
            if is_rune(coin):
                if coin in user_favorites_runes:
                    del user_favorites_runes[coin]  # Delete the rune dictionary
                    removed_runes.append(coin)
            else:
                if coin in user_favorites_coins:
                    user_favorites_coins.remove(coin)
                    removed_coins.append(coin)
    message = ''
    if added_coins or removed_coins:
        favorites_coins[key] = user_favorites_coins if user_favorites_coins else favorites_coins.pop(key, None)
        await save_favorites(favorites_coins, 'coins')
        if added_coins:
            message += f"Added coins to your favorites: {', '.join(added_coins)}\n"
        if removed_coins:
            message += f"Removed coins from your favorites: {', '.join(removed_coins)}\n"
    if added_runes or removed_runes:
        if user_favorites_runes:
            favorites_runes[key] = user_runes_dict
        else:
            favorites_runes.pop(key, None)
        await save_favorites(favorites_runes, 'runes')
        if added_runes:
            message += f"Added runes to your favorites: {', '.join(added_runes)}\n"
        if removed_runes:
            message += f"Removed runes from your favorites: {', '.join(removed_runes)}"
    else:
        message = "No changes were made to your favorites."
    return message

async def manage_coins_command(ctx, coins: str, user_id: str, action: str):
    coins = [coin.strip() for coin in coins.split(',')]
    coins = [await check_coin(coin) if not is_rune(coin) else coin for coin in coins]
    if coins:  # Check if coins list is not empty
        message = await manage_coins(ctx, user_id, coins, action)
        await ctx.edit(content=message)

@bot.slash_command(name="add", description="Add coins to your favorites or a list by name or exact ID")
async def add(ctx, coins: str, get_quant:bool = False, exact_id: bool = False):
    await ctx.defer(ephemeral=True)
    user_id = str(ctx.author.id)
    if get_quant:
        user_data = get_user_data(user_id)
        if user_data is None:
            await ctx.edit(content="add your address using /runes first, coin not added")
            return
        else:
            if 'address' in user_data:
                address = user_data['address']
            else:
                await ctx.edit(content="add your address using /runes first, coin not added")
                return
    global coin_data
    global runes_data
    user_id = str(ctx.author.id)
    coins = coins.split(",") 
    valid_coins = coins.copy()
    for coin in coins:
        if is_rune(coin):
            save = coin
            rune_name = sanitize_rune(coin)
            if coin not in runes_data:
                rune_data = await fetch_rune_data(rune_name)
                if rune_data == {}:
                    await ctx.edit(content=f"The coin {save} you provided is not valid.")
                    valid_coins.remove(save)
                    continue
                else:
                    add_rune_data(user_id, rune_data)
                    if get_quant:
                        rune_data = await get_my_runes(address,coin)
                        add_rune_data(user_id, rune_data)
            valid_coins.remove(save)
            valid_coins.append(rune_name)
              
    coins = valid_coins
    coins_str = ",".join(coin for coin in coins if not isinstance(coin, bool))
    if exact_id:
        # Check if the coin_id exists in coins
        with open('coins.json', 'r', encoding='utf-8') as f:
            coins_data = json.load(f)
        if any(coin['id'] == coins for coin in coins_data):
            # Add the coin to the favorites if it's not already there
            message = await manage_coins(ctx, user_id, [coins], 'add')
            await ctx.edit(content=message)
        else:
            await ctx.edit(content="The coin you provided is not valid.")
    else:
        if coins_str == "":
            return
        await manage_coins_command(ctx, coins_str, user_id, 'add')  # Pass coins_str instead of coins

@bot.slash_command(name="remove", description="Remove coins from your favorites or a list")
async def remove(ctx, coins: str):
    await ctx.defer(ephemeral=True)
    valid_coins = coins.split(',')  # split the string into a list
    for coin in valid_coins:
        if is_rune(coin):
            save = coin
            rune = sanitize_rune(coin)
            valid_coins.remove(save)
            valid_coins.append(rune)
    await manage_coins_command(ctx, ','.join(valid_coins), str(ctx.author.id), 'remove')  # join the list back into a string

def save_alerts(alert, user_id, server_id):
    # Load the existing alerts from the file
    existing_alerts = load_json_file('alerts.json')

    # Update the alerts for the specified user in the specified server
    if server_id not in existing_alerts:
        existing_alerts[server_id] = {}

    if user_id not in existing_alerts[server_id]:
        existing_alerts[server_id][user_id] = []

    # Append the new alert to the list of existing alerts
    existing_alerts[server_id][user_id].append(alert)

    # Write the updated alerts back to the file
    with open('alerts.json', 'w') as f:
        f.write(json.dumps(existing_alerts))

    # Return the updated alerts
    return existing_alerts

async def get_ids(ctx, coin):
    server_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    if is_rune(coin):
        coin_id = coin
    else:
        coin_id = await check_coin(coin)
    return server_id, user_id, coin_id


async def get_alert_type_and_value(target):
    if target.lower() == 'ath':
        return 'ath', None
    elif '%' in target:
        try:
            return 'change', abs(float(target.strip('%')))
        except ValueError:
            return None, None
    else:
        try:
            return 'price', float(target)
        except ValueError:
            return None, None

def get_condition(alert_type, current_price, target_value):
    if alert_type == 'price':
        return '>' if current_price < target_value else '<'
    elif alert_type == 'change':
        return '>'
    else:
        return None

def create_alert(coin_id, alert_type, condition, target_value, cooldown_seconds, channel_id):
    return {
        'coin': coin_id,
        'alert_type': alert_type,
        'condition': condition,
        'target': target_value,
        'cooldown': cooldown_seconds,
        'last_triggered': 0,
        'channel_id': str(channel_id)
    }

async def send_confirmation_message(ctx, new_alert, coin_name):
    cooldown_message = ""
    if new_alert['cooldown'] is not None:
        cooldown_in_hours = new_alert['cooldown'] / 3600
        cooldown_message = f" Cooldown: {cooldown_in_hours:.0f} hours."

    if new_alert['alert_type'] == 'ath':
        await ctx.edit(content=f"ATH alert set for {coin_name}.{cooldown_message}")
    else:
        percentage_symbol = "%" if new_alert['alert_type'] == 'change' else ""
        await ctx.edit(content=f"{new_alert['alert_type'].capitalize()} alert set for {coin_name} {new_alert['condition']} {format_number(new_alert['target'])}{percentage_symbol}.{cooldown_message}")

@bot.slash_command(name="alert", description="Set a price alert for a coin")
async def alert(ctx, coin: str, target: str, cooldown: int = None):
    global coin_data
    global runes_data
    await ctx.defer(ephemeral=True)
    if is_rune(coin):
        coin = sanitize_rune(coin)
    server_id, user_id, coin_id = await get_ids(ctx, coin)
    if not coin_id:
        await ctx.edit(content="Invalid coin")
        return
    alert_type, target_value = await get_alert_type_and_value(target)
    if alert_type is None:
        await ctx.edit(content="Invalid target")
        return
    # Get the current price of the coin to determine direction
    if is_rune(coin):
        current_price = runes_data[coin_id]['current_price']
        coin_name = runes_data[coin_id]['name']  # Use the coin's name
    else:  
        current_price = coin_data[coin_id]['current_price']
        coin_name = coin_data[coin_id]['name']
    condition = get_condition(alert_type, current_price, target_value)
    cooldown_seconds = cooldown * 3600 if cooldown is not None else None
    new_alert = create_alert(coin_id, alert_type, condition, target_value, cooldown_seconds, ctx.channel.id)
    save_alerts(new_alert, user_id, server_id)

    await send_confirmation_message(ctx, new_alert, coin_name)


@bot.slash_command(name="clear", description="Clear all alerts and/or favorites for a user")
async def clear_data(ctx, data_type: str = None):
    await ctx.defer(ephemeral=True)
    server_id = str(ctx.guild.id)  # Get the server ID
    user_id = str(ctx.author.id)

    alert_message = clear_alerts(data_type, server_id, user_id)
    favorite_message = clear_favorites(data_type, user_id)

    # Edit the original deferred message
    if alert_message and favorite_message:
        await ctx.edit(content=f"{alert_message}\n{favorite_message}")
    else:
        await ctx.edit(content=alert_message if alert_message else favorite_message)

def clear_alerts(data_type, server_id, user_id):
    if data_type not in ['alerts', None]:
        return ""

    alerts = load_json_file('alerts.json')
    if server_id in alerts and user_id in alerts[server_id]:
        del alerts[server_id][user_id]  # Remove the user's alerts

        # If no other users in the server, remove the server data too
        if not alerts[server_id]:
            del alerts[server_id]

        # Write the updated alerts back to the file
        with open('alerts.json', 'w') as f:
            f.write(json.dumps(alerts))

        return "All alerts have been cleared."
    else:
        return "No alerts found."

def clear_favorites(data_type, user_id):
    if data_type not in ['favorites', None]:
        return ""

    favorites = load_json_file('favorite_coins.json')
    if user_id in favorites:
        del favorites[user_id]  # Remove the user's favorites

        # Write the updated favorites back to the file
        with open('favorite_coins.json', 'w') as f:
            f.write(json.dumps(favorites))
    favorites = load_json_file('favorite_runes.json')
    if user_id in favorites:
        del favorites[user_id]  # Remove the user's favorites

        # Write the updated favorites back to the file
        with open('favorite_runes.json', 'w') as f:
            f.write(json.dumps(favorites))

    return "All favorites have been cleared."


async def send_alert(channel_id, user_id, coin, message):
    channel = await bot.fetch_channel(int(channel_id))
    await channel.send(f"<@{user_id}> {coin} {message}")
    return time.time()

def check_price_alert(alert, current_price):
    return (alert['condition'] == '>' and current_price > alert['target']) or \
           (alert['condition'] == '<' and current_price < alert['target'])

def check_change_alert(alert, change_24h):
    return abs(change_24h) > alert['target']

def check_ath_alert(alert, ath_date):
    if ath_date is not None:

        ath_date = parse_date(ath_date)
        return (datetime.now() - ath_date).total_seconds() <= 600
    return False

async def check_alerts():
    global coin_data
    global runes_data
    alerts = load_json_file('alerts.json')
    spam_channels = load_json_file('spam_channels.json')

    for server_id, server_alerts in alerts.items():
        for user_id, user_alerts in server_alerts.items():
            new_user_alerts = []  
            for alert in user_alerts:  
                data = runes_data if is_rune(alert['coin']) else coin_data
                if alert['coin'] in data:
                    coin_info = data[alert['coin']]  # Corrected line
                    coin_name = coin_info['name']  # Corrected line
                    current_price = coin_info['current_price']  # Corrected line
                    change_24h = coin_info['change_24h']  # Corrected line
                    ath = coin_info['ath']  # Corrected line
                    ath_date = parse_date(coin_info['ath_date'])               
                    cooldown = alert.get('cooldown')  
                    last_triggered = alert.get('last_triggered', 0)  
                    if cooldown is not None and time.time() - last_triggered < cooldown:
                        continue
                    channel_id = spam_channels.get(server_id, {}).get('channel_id', alert['channel_id'])
                    

                    if alert['alert_type'] == 'price' and check_price_alert(alert, current_price):
                        alert['last_triggered'] = await send_alert(channel_id, user_id, coin_name, f"price is now {alert['condition']} {alert['target']}")
                        if cooldown is None:
                            continue  

                    elif alert['alert_type'] == 'change' and check_change_alert(alert, change_24h):
                        change_type = "up" if change_24h > 0 else "down"
                        alert['last_triggered'] = await send_alert(channel_id, user_id, coin_name, f"is {change_type} {abs(round(change_24h,1))}% in the last 24h")
                        if cooldown is None:
                            continue  

                    elif alert['alert_type'] == 'ath' and check_ath_alert(alert, ath_date):
                        alert['last_triggered'] = await send_alert(channel_id, user_id, coin_name, f"price has reached a new All-Time High of {ath}!")
                        if cooldown is None:
                            continue  

                new_user_alerts.append(alert)

            server_alerts[user_id] = new_user_alerts

    with open('alerts.json', 'w') as f:
        json.dump(alerts, f)
@bot.slash_command(name="set_spam_channel", description="Set the current channel as the server's spam channel")
@commands.has_permissions(manage_channels=True)
async def set_spam_channel(ctx, force_all_messages: bool = False, ephemeral_messages: bool = False):
    await ctx.defer(ephemeral=True)
    server_id = str(ctx.guild.id)  # Get the server ID
    channel_id = str(ctx.channel.id)  # Get the channel ID

    spam_channels = load_json_file('spam_channels.json')

    # Save the spam channel for the server
    spam_channels[server_id] = {
        'channel_id': channel_id,
        'force_all_messages': force_all_messages,
        'ephemeral_messages': ephemeral_messages
    }

    # Write the updated spam channels back to the file
    with open('spam_channels.json', 'w') as f:
        json.dump(spam_channels, f)

    await ctx.edit(content=f"Spam channel set to {ctx.channel.name}. Force ALL messages to this channel: {force_all_messages}. Force most messages invisible (BETA): {ephemeral_messages}")

def get_all_coins_and_runes():
    # Load and extract coins
    with open('favorite_coins.json', 'r') as f:
        coins_data = json.load(f)
    coins_list = [coin for user in coins_data.values() for coin in user]

    # Load and extract runes
    with open('favorite_runes.json', 'r') as f:
        runes_data = json.load(f)
    runes_list = [rune for user in runes_data.values() for rune in user['runes']]

    # Load and extract alerts
    with open('alerts.json', 'r') as f:
        alerts_data = json.load(f)

    for server in alerts_data.values():
        for user in server.values():
            for alert in user:
                if is_rune(alert['coin']):  # Assuming is_rune is a function that checks if a coin is a rune
                    runes_list.append(alert['coin'])
                else:
                    coins_list.append(alert['coin'])

    # Convert lists to sets to remove duplicates, then convert back to lists
    coins_list = list(set(coins_list))
    runes_list = list(set(runes_list))

    return coins_list, runes_list



def save_historical_data():
    global coin_data
    global runes_data
    # Get the current date and time
    now = datetime.now()
    # Check if it's around midnight
    if now.hour == 0 and now.minute <5:
        # Format the current date as a string
        date_str = now.strftime('%Y-%m-%d')

        # Create the file name
        data_file = f'historical/data_{date_str}.json'

        # Check if the file already exists
        if not os.path.exists(data_file):
            # Create a dictionary with both datasets
            data = {'coin_data': coin_data, 'runes_data': runes_data}

            # Dump the data into the file
            with open(data_file, 'w') as f:
                json.dump(data, f)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

@tasks.loop(minutes = 1)  # Create a task that runs every minute
async def update_activity():
    global change_btc  # Declare the variable as global so we can modify it
    coins_list, runes_list = get_all_coins_and_runes()

    if coins_list is None:
        coins_list = ['bitcoin']
    elif len(coins_list) > 249:
        coins_list = coins_list[:249]
    elif 'bitcoin' not in coins_list:
        coins_list.append('bitcoin')
    price_btc, change, gecko = await get_coin_data(coins_list)

    await parse_rune_data(runes_list)
    price_btc = format_number(price_btc,bitcoin=True)
    save_historical_data()
    await check_alerts()

    if not gecko:
        if price_btc == .999:
            return
        else:
            change = change_btc  # Use the last known change
    else:
        change = round(change, 2)
        change_btc = change  # Update the last known change
    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬈{change}%"))
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬊{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} (:skull_crossbones: ⬊{change}% :skull_crossbones:)"))


bot.run(token)
