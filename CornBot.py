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


load_dotenv()
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
            return min(data, key=lambda coin_id: data[coin_id]['market_cap_rank'] if data[coin_id]['market_cap_rank'] is not None else float('inf'))
    else: 
        return False

@bot.slash_command(name="price", description="Show the current price for a coin")
async def price(ctx, coins: str, include_historical: bool = False):
    
    await ctx.defer()
    # Split the coins parameter by commas to get a list of coins
    coins = [coin.strip() for coin in coins.split(',')]
    coins_data = {}
    for coin in coins:
        coin_id = await check_coin(coin)
        if not coin_id:
            continue
        data = await fetch_coin_data([coin_id])
        if data and coin_id in data:
            coins_data[coin_id] = data[coin_id]       
    await display_coins(ctx, coins_data, include_historical = include_historical)

def is_number(n):
    try:
        float(n)
        return True
    except ValueError:
        return False

def round_sig(num, sig_figs = 2):
    if num != 0:
        return round(num, -int(math.floor(math.log10(abs(num))) - (sig_figs - 1)))
    else:
        return 0  # Can't take the log of 0

def format_number(num):
    if num is None or not is_number(num):
        return 0
    else:
        num = float(num)
        if num >= 1e11:
            return f'{num/1e9:,.0f} B'
        elif num >= 1e7:
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
        
async def create_table(coins_data, display_id, include_historical=False):
    if include_historical:
        field_names = ['ID' if display_id else 'Name', 'Price', 'M Cap', 'Δ 24h', 'Δ 7d', 'Δ 30d', 'Δ 1y', 'Δ ATH']
    else:
        field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'M Cap', 'Δ ATH']

    table = PrettyTable()
    table.field_names = field_names
    table.align = 'r'  # right-align data
    table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs

    for coin_id, coin_data in coins_data.items():  # renamed from prices to coin_data
        name = truncate_name(coin_data['name'])
        market_cap = format_number(coin_data['market_cap']) if format_number(coin_data['market_cap']) != 0 else 'N/A'
        price = format_number(coin_data['current_price']) if coin_data['current_price'] else 'N/A'
        change_24h = format_change(coin_data['change_24h'])
        ath_change = format_change(coin_data['ath_change_percentage'])

        if include_historical:
            change_7d = format_change(coin_data.get('change_7d'))
            change_30d = format_change(coin_data.get('change_30d'))
            change_1y = format_change(coin_data.get('change_1y'))
            row_data = [name if not display_id else coin_id, price, market_cap, change_24h, change_7d, change_30d, change_1y, ath_change]
        else:
            row_data = [name if not display_id else coin_id, price, change_24h, market_cap, ath_change]

        table.add_row(row_data)

    return table
def truncate_name(name, max_length=15):
    return name[:max_length-2] + '..' if len(name) > max_length else name

def format_change(change):
    if change is None:
        return 'N/A'
    return f"{'+-'[change < 0]}{abs(change):.1f}%"

async def split_table(table):
    messages = []
    table_str = str(table)
    if len(table_str) > 2000:
        table.del_row(-1)
        messages.append(f'```\n{table}\n```')
    else:
        messages.append(f'```\n{table}\n```')
    return messages

async def display_coins(ctx, coins_data, display_id=False, list_name=None, include_historical=False):
    filtered_coins = {coin_id: coin_data for coin_id, coin_data in coins_data.items()}

    if not filtered_coins:
        await ctx.edit(content='No coins with a market cap of $1 million or more were found.')
        return

    table = await create_table(filtered_coins, display_id, include_historical)
    messages = await split_table(table)

    if list_name:
        messages[0] = f"Displaying coins from the list '{list_name}':\n" + messages[0]

    await ctx.edit(content=messages[0])
    for message in messages[1:]:
        await ctx.send(content=message)
            
@bot.slash_command(name="coins", description="Show current prices for your favorite coins")
async def coins(ctx, list_name: Optional[str] = None, include_historical: Optional[bool] = False):
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
    coin_data = await fetch_coin_data(coins)  # renamed from prices to coin_data
    await display_coins(ctx, coin_data, list_name=list_name, include_historical=include_historical)

@bot.slash_command(name="search", description="Search for coins by name and display their IDs, price, and market cap")
async def search_coins(ctx, query: str, num: Optional[int] = 10):
    await ctx.defer()
    url = f'https://api.coingecko.com/api/v3/search?query={query}'
    matching_coins = await fetch_data_from_api(url)
    matching_ids = [coin['id'] for coin in matching_coins['coins'][:num]]
    coin_data = await fetch_coin_data(matching_ids)
    await display_coins(ctx, coin_data, display_id=True)

def get_emoji(action,coin):
    neutral_emojis = ['<:glasses:958216013529366528> ', '<:scam:1059964673530806283> ', '<:shrug:1203958281094299678>','<a:nfa:1042264955879166003> ' ] # Replace with your actual neutral emojis
    buy_emojis = ['<a:pepelaugh:922704567332917258> ', '<a:buybuybuy:920335813294841966> ', '<:dogeGIGA:839205306042286151> ','<:smoke:929557485210181673> '] + neutral_emojis
    sell_emojis = ['<:harold:826533474886221904> ', '<:bonk:1056641594255736832>','<:cramer:1062188133711626301> ','<:bobo:1016420363829256212> ','<a:sadpepedance:935358551151505469>' ] + neutral_emojis
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

@bot.slash_command(name="ofa", description="Gives Official Financial Advice")
async def ofa(ctx):
    await ctx.defer()
    user_id = str(ctx.author.id)
    favorites = load_favorites()
    coins = get_coins(user_id, favorites)
    coin = random.choice(coins)
    coin_data = await fetch_coin_data([coin])  # renamed from prices to coin_data
    price = coin_data[coin]['current_price']
    name = coin_data[coin]['name']
    leverage = get_leverage()
    action = get_action(leverage)
    emoji = get_emoji(action,coin)
    buy_time, buy_price = get_buy_time_and_price(coin_data, coin, price)  # renamed from prices to coin_data

    await send_advice(ctx, action, name, buy_time, buy_price, leverage, emoji)

def get_coins(user_id, favorites):
    coins = []
    if random.random() < .5:
        for user_favorites in favorites.values():
            coins += user_favorites
    elif user_id in favorites and favorites[user_id]:
        coins = favorites[user_id]
    for coin in ['bitcoin', 'ethereum', 'solana']:
        if coin not in coins:
            coins.append(coin)
    return coins

def get_leverage():
    rand = random.random()
    if rand < .5:
        return 0
    elif rand > .995:
        return None
    else:
        return random.choice([6.9, 20, 42.069, 69, 100, 420])

    
def get_action(leverage):
    return 'BUY' if random.random() < .7 and leverage == 0 else 'LONG' if random.random() < .7 and leverage > 0 else 'SHORT'

def calculate_change_date(change_key):
    if change_key == 'change_24h':
        return 'yesterday'
    elif change_key == 'change_7d':
        return 'a week ago'
    elif change_key == 'change_30d':
        return 'a month ago'
    elif change_key == 'change_1y':
        return 'a year ago'
    else:
        return 'now'

def get_valid_change(coin_data, coin):
    while True:
        change_key = random.choice(['change_24h', 'change_7d', 'change_30d', 'change_1y'])
        change = coin_data[coin].get(change_key)
        if change is not None:
            return change_key, change / 100  # Return the key and the change value as a decimal

def get_buy_time_and_price(coin_data, coin, price):
    rand = random.random()
    if rand < .1:
        change_key, change = get_valid_change(coin_data, coin)
        change_date = calculate_change_date(change_key)
        if change < 0:  # Price decreased
            approx_price = price / (1 - change)
        else:  # Price increased
            approx_price = price / (1 + change)
        return change_date, approx_price
    elif rand < 0.6:
        return 'now', price
    elif rand < 0.75:
        return 'tomorrow', price * (1 + random.uniform(-0.2, 0.2))
    elif rand < 0.9:
        return 'next week', price * (1 + random.uniform(-0.2, 0.2))
    else:
        date = datetime.strptime(coin_data[coin]["ath_date"], '%Y-%m-%dT%H:%M:%S.%fZ')
        date = date.strftime('%B %d, %Y')  # Format the date as 'Month Day, Year'
        return f'on {date}', coin_data[coin]['ath']

async def send_advice(ctx, action, coin, buy_time, buy_price, leverage, emoji):
    if leverage is None:
        await ctx.edit(content=f'Official Financial Advice: Play Purge Game')
    elif leverage > 0:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, {buy_time} at ${format_number(buy_price)}, with {leverage}x leverage. {emoji}')
    else:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, {buy_time} at ${format_number(buy_price)}. {emoji}')

def parse_data(data):
    data = {coin['id']: coin for coin in data}

    parsed_data = {}

    for coin_id, coin in data.items():
        name = coin['name']  # Extract the name
        current_price = coin['current_price']
        ath = coin['ath']
        ath_date = coin['ath_date']
        market_cap = coin['market_cap']
        market_cap_rank = coin['market_cap_rank']
        change_1y = coin.get('price_change_percentage_1y_in_currency')
        change_24h = coin.get('price_change_percentage_24h')
        change_30d = coin.get('price_change_percentage_30d_in_currency')
        change_7d = coin.get('price_change_percentage_7d_in_currency')
        ath_change_percentage = coin.get('ath_change_percentage')

        parsed_data[coin_id] = {
            'name': name,  # Add the name to the parsed data
            'current_price': current_price,
            'market_cap': market_cap,
            'ath': ath,
            'ath_date': ath_date,
            'market_cap_rank': market_cap_rank,
            'change_1y': change_1y,
            'change_24h': change_24h,
            'change_30d': change_30d,
            'change_7d': change_7d,
            'ath_change_percentage': ath_change_percentage,
        }

    return parsed_data

async def fetch_coin_data(coin_ids):
    coin_ids_str = ', '.join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_ids_str}&price_change_percentage=7d%2C30d%2C1y"
    if len(coin_ids) > 100:
        url += f"&per_page={len(coin_ids) + 1}"
    data = await fetch_data_from_api(url)
    parsed_data = parse_data(data)
    return parsed_data

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

async def get_bitcoin_price():
    global change_btc
    existing_alerts = load_json_file('alerts.json')
    coins = list(set([alert['coin'] for server in existing_alerts.values() for user in server.values() for alert in user if isinstance(alert, dict) and 'coin' in alert]))
    coins.append('bitcoin')
    coins = list(set(coins))
    if len(coins) > 250:
        coins = coins[:250]

    coingecko_success = True
    try:
        data = await fetch_coin_data(coins)
    except:
        data = {}
        coingecko_success = False
    if 'bitcoin' not in data:
        data['bitcoin'] = await fetch_bitcoin_price_fallback()

    if coingecko_success and 'change_24h' in data['bitcoin']:
        await check_alerts(data)
        change_btc = data['bitcoin']['change_24h']

    return (data['bitcoin']['current_price'], change_btc, coingecko_success)


def load_favorites():
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
    coins = [coin.strip() for coin in coins.split(',')]
    coins = [await check_coin(coin) for coin in coins]
    message = await manage_coins(ctx, user_id, coins, action, list_name)
    if list_name:
        message = message.replace("Added coins to your favorites", "Added coins").replace("Removed coins from your favorites", "Removed coins")
        message += f" to the list {list_name}" if action == 'add' else f" from the list {list_name}"
    await ctx.edit(content=message)

async def check_list_name(list_name):
    return sum(c.isdigit() for c in list_name) <= 10

@bot.slash_command(name="add", description="Add coins to your favorites or a list by name or exact ID")
async def add(ctx, coins: str, list_name: str = None, exact_id: bool = False):
    await ctx.defer(ephemeral=True)
    user_id = str(ctx.author.id)

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
        if list_name:
            if not await check_list_name(list_name):
                await ctx.send("List name cannot contain more than 10 digits.")
                return
            await manage_coins_command(ctx, coins, list_name, 'add', list_name)
        else:
            await manage_coins_command(ctx, coins, user_id, 'add')

@bot.slash_command(name="remove", description="Remove coins from your favorites or a list")
async def remove(ctx, coins: str, list_name: str = None):
    await ctx.defer(ephemeral=True)
    if list_name:
        if not await check_list_name(list_name):
            await ctx.edit(content="List name cannot contain more than 10 digits.")
            return
        await manage_coins_command(ctx, coins, list_name, 'remove', list_name)
    else:
        await manage_coins_command(ctx, coins, str(ctx.author.id), 'remove')

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

async def send_confirmation_message(ctx, new_alert, coin_id):
    cooldown_message = ""
    if new_alert['cooldown'] is not None:
        cooldown_in_hours = new_alert['cooldown'] / 3600
        cooldown_message = f" Cooldown: {cooldown_in_hours:.0f} hours."

    if new_alert['alert_type'] == 'ath':
        await ctx.edit(content=f"ATH alert set for {coin_id}.{cooldown_message}")
    else:
        percentage_symbol = "%" if new_alert['alert_type'] == 'change' else ""
        await ctx.edit(content=f"{new_alert['alert_type'].capitalize()} alert set for {coin_id} {new_alert['condition']} {format_number(new_alert['target'])}{percentage_symbol}.{cooldown_message}")


@bot.slash_command(name="alert", description="Set a price alert for a coin")
async def alert(ctx, coin: str, target: str, cooldown: int = None):
    await ctx.defer(ephemeral=True)
    server_id, user_id, coin_id = await get_ids(ctx, coin)
    if not coin_id:
        await ctx.edit(content="Invalid coin")
        return
    alert_type, target_value = await get_alert_type_and_value(target)
    if alert_type is None:
        await ctx.edit(content="Invalid target")
        return
    # Get the current price of the coin to determine direction
    coin_data = await fetch_coin_data([coin_id])
    current_price = coin_data[coin_id]['current_price']
    condition = get_condition(alert_type, current_price, target_value)
    cooldown_seconds = cooldown * 3600 if cooldown is not None else None
    new_alert = create_alert(coin_id, alert_type, condition, target_value, cooldown_seconds, ctx.channel.id)
    save_alerts(new_alert, user_id, server_id)

    await send_confirmation_message(ctx, new_alert, coin_id)


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

    favorites = load_json_file('favorites.json')
    if user_id in favorites:
        del favorites[user_id]  # Remove the user's favorites

        # Write the updated favorites back to the file
        with open('favorites.json', 'w') as f:
            f.write(json.dumps(favorites))

        return "All favorites have been cleared."
    else:
        return "No favorites found."

async def send_alert(channel, user_id, coin, message):
    await channel.send(f"<@{user_id}> {coin} {message}")
    return time.time()

def check_price_alert(alert, current_price):
    return (alert['condition'] == '>' and current_price > alert['target']) or \
           (alert['condition'] == '<' and current_price < alert['target'])

def check_change_alert(alert, change_24h):
    return abs(change_24h) > alert['target']

def check_ath_alert(alert, ath_date):
    if ath_date is not None:
        ath_date = datetime.fromisoformat(ath_date.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ath_date).total_seconds() <= 600
    return False

async def check_alerts(data):
    alerts = load_json_file('alerts.json')
    spam_channels = load_json_file('spam_channels.json')

    for server_id, server_alerts in alerts.items():
        for user_id, user_alerts in server_alerts.items():
            for alert in user_alerts.copy():  # Iterate over a copy of the list
                if alert['coin'] in data:
                    current_price = data[alert['coin']]['current_price']
                    change_24h = data[alert['coin']]['change_24h']
                    ath = data[alert['coin']]['ath']  # Update ATH
                    ath_date = datetime.strptime(data[alert['coin']]['ath_date'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M+00:00")
                    cooldown = alert.get('cooldown')  # Get the cooldown, or None if it's not present
                    last_triggered = alert.get('last_triggered', 0)  # Get the last_triggered, or 0 if it's not present
                    if cooldown is not None and time.time() - last_triggered < cooldown:
                        continue
                    channel_id = spam_channels.get(server_id, {}).get('channel_id', alert['channel_id'])
                    channel = await bot.fetch_channel(int(channel_id))

                    if alert['alert_type'] == 'price' and check_price_alert(alert, current_price):
                        alert['last_triggered'] = await send_alert(channel, user_id, alert['coin'], f"price is now {alert['condition']} {alert['target']}")

                    elif alert['alert_type'] == 'change' and check_change_alert(alert, change_24h):
                        change_type = "up" if change_24h > 0 else "down"
                        alert['last_triggered'] = await send_alert(channel, user_id, alert['coin'], f"is {change_type} {abs(round(change_24h,1))}% in the last 24h")

                    elif alert['alert_type'] == 'ath' and check_ath_alert(alert, ath_date):
                        alert['last_triggered'] = await send_alert(channel, user_id, alert['coin'], f"price has reached a new All-Time High of {ath}!")

                    if cooldown is None:
                        user_alerts.remove(alert)  # Remove the alert

    # Save the alerts
    with open('alerts.json', 'w') as f:
        json.dump(alerts, f)

@bot.slash_command(name="set_spam_channel", description="Set the current channel as the server's spam channel")
@commands.has_permissions(manage_channels=True)
async def set_spam_channel(ctx, force_all_messages: bool = False, ephemeral_messages: bool = False):
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

    await ctx.send(f"Spam channel set to {ctx.channel.name}.")
        
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()  # Start the task as soon as the bot is ready

@tasks.loop(minutes = 1)  # Create a task that runs every minute
async def update_activity():
    global change_btc  # Declare the variable as global so we can modify it
    price_btc, change, gecko = await get_bitcoin_price()
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


