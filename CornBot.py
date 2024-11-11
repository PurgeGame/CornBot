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
from bs4 import BeautifulSoup
from dateutil.parser import parse

load_dotenv()
coin_data = {}
runes_data = {}
all_transactions = {}
triggered_tx_ids = {}
if os.path.exists('all_transactions.json'):
    try:
        with open('all_transactions.json', 'r') as f:
            all_transactions = json.load(f)
    except json.JSONDecodeError:
        print("Error: Invalid JSON file")

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
    field_names = [ 'Name', 'Price', 'Δ 24h', 'M Cap', 'Vol', 'Mints', '$/Mint','Value', 'S']
    table = PrettyTable()
    table.field_names = field_names
    table.align = 'r'  # right-align data
    table.align['Name'] = 'l'  # left-align IDs
    table.align['Sym'] = 'l'  # left-align IDs

    total_value = 0
    rows = []  # Store the rows here first
    skipped = 0
    for coin_id, rune_data in runes.items():
        
        owned_runes = check_coin_quantity(user_id, coin_id)
        quantity_owned = float(owned_runes['balance']) if owned_runes is not None and 'balance' in owned_runes else 0
        unformatted_price = rune_data['current_price']
        name = rune_data['name'].replace("•", " ")
        symbol = rune_data['symbol'] if rune_data['symbol'] else ''
        name = truncate_name(name,20)
        
        market_cap = format_number(rune_data['market_cap']) if format_number(rune_data['market_cap']) != 0 else 'N/A'
        price = format_number(rune_data['current_price']) if rune_data['current_price'] else 'N/A'
        change_24h = format_change(rune_data['change_24h']) if rune_data['change_24h'] else 'N/A'
        sat_price = float(coin_data['bitcoin']['current_price']) / 100000000
        volume_24h = format_number(int(int(rune_data['volume_24h']) * sat_price), vol = True) if rune_data['volume_24h'] else 'N/A'
        volume_7d = format_number(int(rune_data['volume_7d']) * sat_price) if rune_data['volume_7d'] else 'N/A'
        volume_24h_calc = int(rune_data['volume_24h']) * sat_price if rune_data['volume_24h'] else 'N/A'
        
        amount = rune_data.get('mint_amount', 'N/A')
        amount = float(str(amount).replace(',', '')) if amount != 'N/A' else 'N/A'
        if amount != 'N/A':
            try:
                mints_owned = quantity_owned / amount
            except ValueError:
                mints_owned = quantity_owned
        else:  
            mints_owned = quantity_owned

        try:
            mint_price = format_number_with_symbol( unformatted_price * sat_price * amount,'USD') if amount != 'N/A' else 'N/A'
            value = format_number_with_symbol(quantity_owned * unformatted_price * sat_price,'USD',True,bitcoin=True) if quantity_owned is not None and price != 'N/A' else 'N/A'
        except ValueError:
            value = 'N/A'
            mint_price = 'N/A'

        if volume_24h == 'N/A' or rune_data.get('volume_24h', 0) < 1000000:
            if volume_7d == 'N/A' or rune_data.get('volume_7d', 0) < 3000000:
                volume_24h = 0
                price = 'N/A'
                market_cap = 'N/A'
                change_24h = 'N/A'
                value = 'N/A'
                skipped+=1
                continue
        try:
            if value != 'N/A':
                total_value += quantity_owned * unformatted_price * sat_price
        except ValueError:
            total_value = 0

        if amount != 'N/A':
            try:
                mints_owned = quantity_owned / amount
            except ValueError:
                mints_owned = quantity_owned
        if mints_owned != 'N/A':
            quantity_owned = mints_owned
        if volume_24h_calc != 'N/A':
            if volume_24h_calc < 1000:
                volume_24h = '<1k'
        else:
            volume_24h = '<1k'
        quantity_owned = format_number(quantity_owned) if quantity_owned is not None else '0'
        row_data = [name, price, change_24h, market_cap, volume_24h, quantity_owned, mint_price, value,symbol]
        rows.append(row_data)  # Add the row data to the list

    # Sort the rows by value (assuming value is a float)
    rows.sort(key=lambda row: convert_to_float(row[-2].replace(',', '').replace('$', '')) if row[-2] != 'N/A' else 0, reverse=True)

    counter = 0  # Reset the counter
    # Add the sorted rows to the table
    for row in rows:
        # Alternate the case of the name
        row[0] = row[0].upper() if counter % 2 == 0 else row[0].lower()
        table.add_row(row)
        counter += 1

    ath = False
    with open('favorite_runes.json', 'r+') as f:
        favorite_runes = json.load(f)
        if 'total_value' not in favorite_runes[user_id] or total_value > favorite_runes[user_id]['total_value']:
            favorite_runes[user_id]['total_value'] = total_value
            f.seek(0)  # Move the cursor to the beginning of the file
            json.dump(favorite_runes, f, indent=4)
            f.truncate()  # Remove any remaining content
            ath = True

    return table,total_value,ath,skipped

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
    table, total_value,ath,skipped = await create_table_runes(runes_data, str(ctx.author.id))
    messages = await split_table(table)
    total_value = format_number_with_symbol(total_value,'USD',True,bitcoin=True)
    await ctx.edit(content=messages[0])
    for message in messages[1:]:
        await ctx.send(content=message)

    # Send a message about the total value
    await ctx.send(content=(f"Skipped {skipped} runes with no volume. " if skipped > 0 else "") + (f'Total portfolio value: {total_value}, a new ATH!' if ath else f'Total portfolio value: {total_value}'))
            
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
    await ctx.defer()
    global runes_data
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
        'balance': float(rune_data['formattedBalance'])
    }

    # Write the updated data back to the JSON file
    with open('favorite_runes.json', 'w') as f:
        json.dump(user_data, f, indent=4)

@bot.slash_command(name="search", description="Search for coins by name and display their IDs, price, and market cap")
async def search_coins(ctx, query: str, num: Optional[int] = 10):
    global runes_data
    await ctx.defer()
    coin_data = {}
    if is_rune(query):
        rune_id = sanitize_rune(query)
        if rune_id:
            # Iterate over the data
            for id, item in runes_data.items():
                # Check if the ID contains the search string
                if rune_id in id:
                    # Add the item to the dictionary
                    coin_data[id] = item
        await display_runes(ctx, coin_data)
    else: 
        url = f'https://api.coingecko.com/api/v3/search?query={query}'
        matching_coins = await fetch_data_from_api(url)
        matching_ids = [coin['id'] for coin in matching_coins['coins'][:num]]
        
        if not matching_ids:
            await ctx.edit(content="No matching coins found.")
            return

        coin_data = await parse_data(matching_ids)
        await display_coins(ctx, coin_data, display_id=True)


@bot.slash_command(name="ofa", description="Gives Official Financial Advice")
async def ofa(ctx):
    await ctx.defer()
    global coin_data
    global runes_data
    user_id = str(ctx.author.id)
    #print_favorite_runes(user_id)
    leverage = get_leverage()
    if leverage:
        action = get_action(leverage)
    else:
        action = 'BUY'
    
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
    if isinstance(rune_list, str):
        rune_list = [rune_list]

    for rune in rune_list:
        if not runes_data.get(rune):
            await add_mint_data(rune)
        else:
            if runes_data[rune].get('divisibility') is None:
                await add_mint_data(rune)
        new_data = await fetch_rune_data(rune)  # Assuming fetch_rune_data is a function that fetches data for a rune
        coin_id = new_data.get('rune', None)
        symbol = new_data.get('symbol', None)
        name = new_data.get('name', None)
        number = new_data.get('runeNumber', None)
        current_price = float(new_data.get('floorUnitPrice', {}).get('formatted', '0'))  # Convert from BTC to sats
        market_cap_in_btc = new_data.get('marketCap', 0)
        volume_24h = new_data.get('volume', {}).get('1d', 0)
        volume_7d = new_data.get('volume', {}).get('7d', 0)
        if volume_24h < 1000000 and volume_7d < 3000000:
            current_price = 0
        # Convert the market cap from Bitcoin to dollars
        btc_price_in_usd = coin_data['bitcoin']['current_price']
        market_cap_in_usd = market_cap_in_btc * btc_price_in_usd
        if not runes_data[rune].get('mint_amount'):
            mint_amount = 1
        else:
            mint_amount = runes_data[rune].get('mint_amount')


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

        runes_data[coin_id]['price_list'].append(round_sig(current_price,3))

        # Calculate the percentage change in the current price versus the oldest data in the price list
        # Only when the price list has a full 24 hours of data
        if coin_id in runes_data and 'price_list' in runes_data[coin_id] and len(runes_data[coin_id]['price_list']) >= 23*60 and runes_data[coin_id]['price_list'][0] != 0:
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
            'volume_7d': volume_7d,
            'mint_amount': mint_amount,
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



async def fetch_rune_data(rune_name,type = 'price',offset = 0):
    if type == 'transactions':
        url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/activities/{rune_name}?offset={offset}"
    else:
        url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/market/{rune_name}/info"
    headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}

    async with aiohttp.ClientSession() as session:

        async with session.get(url, headers=headers) as response:
            if response.status == 200 and response.content_type == 'application/json':
                data = await response.json()

                if data:
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

async def manage_coins_command(ctx, coins: str, user_id: str, action: str, quantity: Optional[bool] = False):
    coins = [coin.strip() for coin in coins.split(',')]
    coins = [await check_coin(coin) if not is_rune(coin) else coin for coin in coins]
    if coins:  # Check if coins list is not empty
        message = await manage_coins(ctx, user_id, coins, action)
        if not quantity:
            await ctx.edit(content=message)

@bot.slash_command(name="add", description="Add coins to your favorites or a list by name or exact ID")
async def add(ctx, coins: str, get_quant:bool = False, exact_id: bool = False):
    await ctx.defer(ephemeral=True)
    global coin_data
    global runes_data
    user_id = str(ctx.author.id)
    coins = coins.split(",")
    quant = False
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
            for rune in coins:
                rune = sanitize_rune(rune)           
                rune_data = await get_my_runes(address,rune)
                if rune_data == {}:
                    await ctx.edit(content=f"{rune} not found.")
                    continue
                add_rune_data(user_id, rune_data)
                balance = rune_data.get('formattedBalance', 0)

                mint_quant = float(balance) / float(runes_data.get(rune, {}).get('mint_amount', 1))

                await ctx.edit(content=f"updated {rune} quantity: {mint_quant} mints")
                quant = True

    user_id = str(ctx.author.id)

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
        await manage_coins_command(ctx, coins_str, user_id, 'add', quantity = quant)  # Pass coins_str instead of coins

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

def get_latest_transaction_date(transactions):
    # Parse the dates and convert them to datetime objects
    dates = [datetime.strptime(txn['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ") for txn in transactions]

    # Get the latest date
    latest_date = max(dates)

    return latest_date

def filter_transactions(transactions, kind,rune):
    return [txn for txn in transactions if txn['kind'] == kind and txn['rune'] == rune]


def snipe_filter(rune, transactions):
    global runes_data
    if 'divisibility' in runes_data[rune]:
        divisibility = 10** int(runes_data[rune]['divisibility'])
    else:
        return []

    # Get the current price of the rune
    current_price = runes_data.get(rune, {}).get('current_price')

    # Check if the current price is not None
    if current_price is None:
        print(f"No current price found for rune: {rune}")
        return []

    # Initialize an empty list to store the transactions where the price per unit is below the current price
    below_current_price_transactions = []

    # Iterate over the transactions
    for txn in transactions:
        price = float(txn['listedPrice'])  # price in satoshis
        amount = float(txn['amount']) / divisibility

        # Check if btcUsdPrice is not None
        if txn['btcUsdPrice'] is None:
            #print(f"btcUsdPrice is None for transaction: {txn}")
            continue

        # Convert btcUsdPrice to float
        btc_usd_price = float(txn['btcUsdPrice']) / 1e8

        # Calculate the price per unit for the transaction
        price_per_unit = price / amount
        price_ratio = price_per_unit / current_price

        # Check if the price per unit is below the current price
        if price_ratio < 0.95:
            # If it is, add the transaction to the list
            txn['price_per_unit'] = price_per_unit
            txn['price_ratio'] = price_ratio
            below_current_price_transactions.append(txn)

    # Initialize an empty list to store the transactions where the total value at the new current price is more than $200
    valuable_transactions = []

    # Iterate over the transactions where the price per unit is below the current price
    for txn in below_current_price_transactions:
        price = float(txn['listedPrice'])  # price in satoshis
        amount = float(txn['amount']) / divisibility  # Recalculate amount for each transaction

        # Convert btcUsdPrice to float
        btc_usd_price = float(txn['btcUsdPrice']) / 1e8

        # Calculate the total value at the current price
        current_value = amount * current_price  # What it would be worth at the current price
        total_value_at_current_price = current_value - price  # The difference in satoshis

        # Check if the total value is more than $100
        total_value_at_current_price_usd = total_value_at_current_price * btc_usd_price
        if total_value_at_current_price_usd > 100:
            # If it is, add the total value to the transaction data
            txn['total_value'] = total_value_at_current_price_usd

            # Add the transaction to the list
            valuable_transactions.append(txn)

            print(f"Snipe found for {rune} with total value of {format_number(total_value_at_current_price_usd)} at price of {format_number(txn['price_per_unit'] * btc_usd_price)}. Transaction ID: {txn['mempoolTxId']}")

    return valuable_transactions

def snipe_check(rune, buys, sold):
    global runes_data

    # Create a set of the selling transactions' txIds and mempoolTxIds
    selling_set = {txn.get('txId', '') for txn in sold if txn.get('rune', '') == rune}
    selling_set.update({txn.get('mempoolTxId', '') for txn in sold if txn.get('rune', '') == rune})

    # Create a dictionary of the buying transactions' mempoolTxIds
    buying_dict = {}
    for buy in buys:
        mempoolTxId = buy.get('mempoolTxId', '')
        if mempoolTxId not in buying_dict and buy.get('rune', '') == rune:
            buying_dict[mempoolTxId] = buy

    # Filter the buying transactions to get only the ones that haven't been sold and don't have duplicate mempoolTxIds
    unsold_orders = [buy for buy in buying_dict.values() if buy.get('txId', '') not in selling_set and buy.get('mempoolTxId', '') not in selling_set]

    # Filter out transactions that are more than an hour old
    unsold_orders = [order for order in unsold_orders if parse(order['createdAt']).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(hours=1)]
    snipes = snipe_filter(rune,unsold_orders)

    return snipes




async def secondary_check_price_change(rune):
    global runes_data 
    global all_transactions
    if 'divisibility' not in runes_data[rune]:
        return
    else:
        divisibility = int(runes_data[rune]['divisibility'])
    if runes_data.get(rune,{}).get('volume_24h',0) <= 1000000:
        return
    c=0
    while True:
        new_data = await fetch_rune_data(rune,'transactions',c*100)
        # Check if new_data is empty
        if not new_data:
            break
        # Add the new transactions to the dictionary
        all_transactions.update({txn['id']: txn for txn in new_data if datetime.now(timezone.utc) - parse(txn['createdAt']) <= timedelta(hours=2)})
        # Check if any of the new transactions are already in the dictionary
        if any(txn['id'] in all_transactions for txn in new_data):
            break
        # Check if any of the transactions are more than 2 hours old
        if any(datetime.now(timezone.utc) - parse(txn['createdAt']) > timedelta(hours=2) for txn in new_data):
            break
        c+=1

# Save the transactions to the JSON file
    with open('your_file.json', 'w', encoding='utf-8') as f:
        json.dump(all_transactions, f)

        buys = filter_transactions(all_transactions.values(), 'buying_broadcasted',rune)

        sold = filter_transactions(all_transactions.values(),'sent',rune)

        # listings = filter_transactions(all_transactions.values(),'create_sell_order')
        # cancels = filter_transactions(all_transactions.values(),'order_cancelled')


        # Create a set of the selling transactions
    
    snipes = snipe_check(rune,buys,sold)
    
    # Calculate the number of runes and the price per rune for each snipe
    snipe_info = [
        {
            'rune': rune,
            'txId': snipe['txId'],
            'mempoolTxId': snipe['mempoolTxId'],
            'total_value': snipe.get('total_value', 'N/A'),
            'number_of_runes': float(snipe['amount']) / (10 ** divisibility),
            'number_of_mints': float(snipe['amount']) / (10 ** divisibility) / runes_data[rune]['mint_amount'] if 'mint_amount' in runes_data[rune] and runes_data[rune]['mint_amount'] is not None else None,
            'price_per_rune': float(snipe['listedPrice']) / (float(snipe['amount']) / (10 ** divisibility)),
            'price per mint': float(snipe['listedPrice']) / (float(snipe['amount']) / (10 ** divisibility)) * runes_data[rune]['mint_amount'] * float(snipe['btcUsdPrice']) / 1e8 if 'mint_amount' in runes_data[rune] and runes_data[rune]['mint_amount'] is not None else None,
            'total_price': float(snipe['listedPrice']) * float(snipe['btcUsdPrice']) / 1e8
        }
        for snipe in snipes
]

    return snipe_info

async def add_mint_data(rune):
    global runes_data
    # Load data from rune_mint_data.json
    with open('rune_mint_data.json', 'r') as f:
        mint_data = json.load(f)
    # Check if the rune exists in the mint data
    if rune not in runes_data:
        runes_data[rune] = {}
    if rune in mint_data:
        # The rune exists in the mint data
        # Add the mint data to runes_data
        runes_data[rune]['supply'] = float(mint_data[rune]['supply'])
        # Extract the number from the amount data
        amount = mint_data[rune]['mint_amount']
        if amount == 'na':
            runes_data[rune]['mint_amount'] = None
        else:
            runes_data[rune]['mint_amount'] = float(amount)
        # Convert the divisibility data to an integer
        runes_data[rune]['divisibility'] = int(mint_data[rune]['divisibility'])
    else:
        # The rune does not exist in the mint data
        # Scrape the data from the webpage
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://ordinals.com/rune/{rune}') as response:
                soup = BeautifulSoup(await response.text(), 'html.parser')
                dl_tag = soup.find('dl')
                
                if dl_tag is None:
                    print(f"Error: 'dl' tag not found for rune {rune}")
                    runes_data[rune]['mint_amount'] = 0  # Default value
                    return
                
                runes_data[rune]['mint_amount'] = 0  # Default value
                for dt, dd in zip(dl_tag.find_all('dt'), dl_tag.find_all('dd')):
                    key = dt.text.strip()
                    value = dd.text.strip()
                    if key == 'supply':
                        supply = value.split()[0]
                        runes_data[rune]['supply'] = float(supply)
                    elif key == 'amount':
                        amount = value.split()[0]
                        runes_data[rune]['mint_amount'] = float(amount)
                    elif key == 'divisibility':
                        runes_data[rune]['divisibility'] = int(value)

async def send_snipe_message(snipe):
    global runes_data
    channel_id = 866304139741888573  # Replace with your channel ID
    global triggered_tx_ids

    # Check if the transaction ID is in the dictionary of triggered transaction IDs
    if snipe['txId'] in triggered_tx_ids:
        # If it is, return without sending a message
        return

    # If it's not, add it to the dictionary with the current timestamp
    triggered_tx_ids[snipe['txId']] = datetime.now()

    channel = await bot.fetch_channel(int(channel_id))
    sniper_role_id = "1249491464543666247" 

    if snipe['total_value'] > 500:
        await channel.send(
            f"<@&{sniper_role_id}> ${format_number(snipe['total_value'])} <:snipe:919674042661892108>    Cost - ${format_number(snipe['total_price'])}.\n"
            f"{runes_data[snipe['rune']]['symbol']}{format_number(snipe['number_of_mints'] or snipe['number_of_runes'])} {snipe['rune']} at {format_number(snipe['price_per_rune'])} sat -"
            + (f" ${format_number(snipe['price per mint'])} per mint - BETA WARNING: DYOR, math may be wrong" if snipe['price per mint'] is not None else "BETA WARNING: DYOR, math may be wrong")
            + f"\n{snipe['txId']}. or maybe {snipe['mempoolTxId']}."
        )
    else:
        await channel.send(
            f"${format_number(snipe['total_value'])} <:snipe:919674042661892108>    Cost - ${format_number(snipe['total_price'])}.\n"
            f"{runes_data[snipe['rune']]['symbol']}{format_number(snipe['number_of_mints'] or snipe['number_of_runes'])} {snipe['rune']} at {format_number(snipe['price_per_rune'])} sat -"
            + (f" ${format_number(snipe['price per mint'])} per mint - BETA WARNING: DYOR, math may be wrong" if snipe['price per mint'] is not None else "BETA WARNING: DYOR, math may be wrong")
            + f"\n{snipe['txId']}. or maybe {snipe['mempoolTxId']}."
        )

async def cleanup_old_tx():
    global triggered_tx_ids

    # Define the threshold for old transactions (e.g., 1 day)
    threshold = timedelta(hours = 2)

    # Get the current time
    now = datetime.now()

    # Remove the transactions that are older than the threshold
    triggered_tx_ids = {tx_id: timestamp for tx_id, timestamp in triggered_tx_ids.items() if now - timestamp <= threshold}




# Add a dictionary to store the last alert time for each rune
last_alert_times = {}

async def check_price_change():
    global runes_data
    global coin_data
    global last_alert_times

    for rune, data in runes_data.items():
        if 'price_list' not in data:
            print(f"Error: 'price_list' key not found for rune {rune}")
            continue

        current_price = data['price_list'][-1]  # Fetch the most recent price
        old_price_1m = data['price_list'][-2] if len(data['price_list']) >= 2 else None  # Get the price from 1 minute ago
        old_price_5m = data['price_list'][-6] if len(data['price_list']) >= 6 else None  # Get the price from 5 minutes ago

        alert_5m = False  # Flag to check if 5-minute alert is sent

        # Check for 10% increase over the last 5 minutes
        if old_price_5m is not None and old_price_5m != 0:
            price_change_5m = current_price - old_price_5m
            change_percentage_5m = price_change_5m / old_price_5m * 100

            last_alert_time = last_alert_times.get(rune)
            if change_percentage_5m > 25 and (last_alert_time is None or datetime.now() - last_alert_time > timedelta(minutes=6)):
                await send_price_change_alert(rune, change_percentage_5m, current_price, '5m')
                last_alert_times[rune] = datetime.now()
                alert_5m = True

        # Check for 5% increase over the last minute
        if not alert_5m and old_price_1m is not None and old_price_1m != 0:
            price_change_1m = current_price - old_price_1m
            change_percentage_1m = price_change_1m / old_price_1m * 100

            if change_percentage_1m > 20:
                await send_price_change_alert(rune, change_percentage_1m, current_price, '1m')

async def send_price_change_alert(rune, change_percentage, current_price, time_period):
    channel_id = 866304139741888573  # Replace with your channel ID
    channel = await bot.fetch_channel(int(channel_id))

    snipes = await secondary_check_price_change(rune)
    if snipes:
        for snipe in snipes:
            await send_snipe_message(snipe)
    if 'mint_amount' in runes_data[rune] and runes_data[rune]['mint_amount'] is not None:
        price_per_mint = format_number(current_price * runes_data[rune]['mint_amount'] * coin_data['bitcoin']['current_price'] / 1e8)
        await channel.send(f'The price of {rune} has increased by {format_change(change_percentage)} to {format_number(current_price)} sats in the last {time_period}. The price per mint is now ${price_per_mint}.')
    else:
        await channel.send(f'The price of {rune} has increased by {format_change(change_percentage)} to {format_number(current_price)} sats in the last {time_period}.')



def save_historical_data():
    global coin_data
    global runes_data
    # Get the current date and time
    now = datetime.now()

    date_str = now.strftime('%Y-%m-%d')

    # Create the file name
    data_file = f'historical/data_{date_str}.json'

    # Create a dictionary with both datasets
    data = {'coin_data': coin_data, 'runes_data': runes_data}

    # Dump the data into the file
    with open(data_file, 'w') as f:
        json.dump(data, f)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

loop_counter = 0  # Initialize the counter outside the loop

@tasks.loop(minutes = 1)  # Create a task that runs every minute
async def update_activity():
    global change_btc  # Declare the variable as global so we can modify it
    global loop_counter  # Declare the counter as global so we can modify it

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
    await check_price_change()

    # Increment the counter


    # Check if it's the 5th iteration
    if loop_counter % 3 == 0:
        loop_counter = 0  # Reset the counter
        for rune in runes_data:
            snipes = await secondary_check_price_change(rune)
            if snipes:
                for snipe in snipes:
                    await send_snipe_message(snipe)
        await cleanup_old_tx()
    loop_counter += 1
  

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
