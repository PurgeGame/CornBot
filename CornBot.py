import discord
from discord.ext import tasks, commands
import os
import json
import math
from prettytable import PrettyTable
import aiohttp
import random
from dotenv import load_dotenv
from typing import Optional
import asyncio
import time


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
change_btc = None



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
    table.field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'Market Cap', 'Δ ATH']
    table.align = 'r'  # right-align data
    table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs

    # Filter coins with market cap >= 1 million
    filtered_coins = {coin_id: coin_data for coin_id, coin_data in coins_data.items()}# if coin_data['market_cap'] and coin_data['market_cap'] >= 1000000}

    messages = []
    current_message = ''

    for coin_id, prices in filtered_coins.items():
        market_cap = format_number(prices['market_cap']) if format_number(prices['market_cap']) != 0 else 'N/A'
        price = format_number(prices['current_price']) if prices['current_price'] else 'N/A'
        change = f"{'+-'[prices['price_change_percentage_24h'] < 0]}{abs(prices['price_change_percentage_24h']):.1f}" if prices['price_change_percentage_24h'] else 'N/A'
        ath_change = f"{prices['ath_change_percentage']:02.0f}%" if prices['ath_change_percentage'] else 'N/A'

        name_or_id = coin_id[:12] + '..' if not display_id and len(coin_id) > 12 else coin_id
        table.add_row([name_or_id, price, f'{change}%', f'{market_cap}', ath_change])

        # Check if the table fits within the limit
        table_str = str(table)
        if len(table_str) > 2000:
            # If it doesn't fit, remove the last row and add the table to the messages
            table.del_row(-1)
            messages.append(current_message + f'```\n{table}\n```')
            # Create a new table with the row that didn't fit
            table = PrettyTable()
            table.field_names = ['ID' if display_id else 'Name', 'Price', 'Δ 24h', 'Market Cap', 'Δ ATH']
            table.align = 'r'  # right-align data
            table.align['ID' if display_id else 'Name'] = 'l'  # left-align IDs
            table.add_row([name_or_id, price, f'{change}%', f'{market_cap}', ath_change])
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
    matching_ids = [coin['id'] for coin in matching_coins['coins'][:num]]
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


@bot.slash_command(name="ofa", description="Gives Official Financial Advice")
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
        leverage = random.choice([6.9, 20, 42.069, 69, 100, 420])
    # Decide whether to buy or sell
    action = 'BUY' if random.random() < .7 and leverage == 0 else 'LONG' if random.random() < .7 and leverage > 0 else 'SHORT'
    emoji = get_emoji(action,coin)
    # Send the suggestion
    if leverage > 0:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, NOW at ${price}, with {leverage}x leverage. {emoji}')
    else:
        await ctx.edit(content=f'Official Financial Advice: {action} {coin}, NOW at ${price}. {emoji}')

async def get_bitcoin_price():
    # Load the existing alerts from the file
    existing_alerts = load_json_file('alerts.json')

    # Get the list of unique coins
    coins = list(set([alert['coin'] for server in existing_alerts.values() for user in server.values() for alert in user if isinstance(alert, dict)]))

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coins)}&vs_currencies=usd&include_24hr_change=true"
    coingecko_success = True
    try:
        data = await fetch_data_from_api(url)
    except:
        data = {}
        coingecko_success = False

    if 'bitcoin' not in data:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get('https://api.coindesk.com/v1/bpi/currentprice/BTC.json') as response:
                    data_btc = await response.json()
                    data['bitcoin'] = {'usd': int(data_btc['bpi']['USD']['rate_float']), 'usd_24h_change': 0}
            except:
                try:
                    async with session.get('https://api.coinbase.com/v2/prices/BTC-USD/spot') as response:
                        data_btc = await response.json()
                        data['bitcoin'] = {'usd': int(float(data_btc['data']['amount'])), 'usd_24h_change': 0}
                except:
                    data['bitcoin'] = {'usd': .999, 'usd_24h_change': 0}

    if coingecko_success: await update_alerts_with_coin_data(data)

    price_btc = data['bitcoin']['usd']
    change_btc = data['bitcoin']['usd_24h_change']

    return (price_btc, change_btc, coingecko_success)

async def update_alerts_with_coin_data(data):
    alerts = load_json_file('alerts.json')

    for server_id, server_alerts in alerts.items():
        for user_id, user_alerts in server_alerts.items():
            for alert in user_alerts:
                if alert['coin'] in data:
                    alert['current_price'] = data[alert['coin']]['usd']
                    alert['usd_24h_change'] = data[alert['coin']]['usd_24h_change']

    with open('alerts.json', 'w') as f:
        json.dump(alerts, f)

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

def save_alerts(alerts, user_id, server_id, delete=False):
    # Load the existing alerts from the file
    existing_alerts = load_json_file('alerts.json')

    # Update the alerts for the specified user in the specified server
    if server_id not in existing_alerts:
        existing_alerts[server_id] = {}

    if delete:
        # Delete the user's alerts
        if user_id in existing_alerts[server_id]:
            del existing_alerts[server_id][user_id]
            # If no other users in the server, remove the server data too
            if not existing_alerts[server_id]:
                del existing_alerts[server_id]
    else:
        # Replace the user's alerts
        existing_alerts[server_id][user_id] = alerts

    # Write the updated alerts back to the file
    with open('alerts.json', 'w') as f:
        f.write(json.dumps(existing_alerts))

    # Return the updated alerts
    return existing_alerts

@bot.slash_command(name="alert", description="Set a price alert for a coin")
async def alert(ctx, coin: str, target: str, cooldown: int = None):
    await ctx.defer(ephemeral=True)
    server_id = str(ctx.guild.id)  # Get the server ID
    user_id = str(ctx.author.id)
    coin_id = await check_coin(coin)
    if not coin_id:
        await ctx.send(content="Invalid coin", ephemeral=True)
        return

    # Determine the alert type and target value based on the target argument
    if '%' in target:
        alert_type = 'change'
        target_value = abs(float(target.strip('%')))  # Remove the '%' and convert to float
    else:
        alert_type = 'price'
        target_value = float(target)

    # Fetch the current price of the coin
    coin_data = await get_prices([coin])
    current_price = coin_data[coin]['current_price']

    # Determine the condition based on the current price and target value
    if alert_type == 'price':
        if current_price < target_value:
            condition = '>'
        else:
            condition = '<'
    else:
        condition = '>'

    cooldown_seconds = cooldown * 3600 if cooldown is not None else None

    new_alert = {
        'coin': coin,
        'alert_type': alert_type,
        'condition': condition,
        'target': target_value,
        'current_price': current_price,
        'usd_24h_change': None,
        'cooldown': cooldown_seconds,
        'last_triggered': 0,
        'channel_id': str(ctx.channel.id)  # Save the channel ID
    }   

    alerts = [new_alert]
    save_alerts(alerts, user_id, server_id)  # Include the server ID in the save_alerts function call

    if new_alert['cooldown'] is None:
        if alert_type == 'change':
            await ctx.edit(content=f"{alert_type.capitalize()} alert set for {coin} {condition} {target_value:.0f}%. This is a one-time alert.")
        else:
            await ctx.edit(content=f"{alert_type.capitalize()} alert set for {coin} {condition} {target_value:.0f}. This is a one-time alert.")
    else:
        cooldown_in_hours = new_alert['cooldown'] / 3600  # Convert seconds to hours
        if alert_type == 'change':
            await ctx.edit(content=f"{alert_type.capitalize()} alert set for {coin} {condition} {target_value:.0f}%. Cooldown: {cooldown_in_hours:.0f} hours.")
        else:
            await ctx.edit(content=f"{alert_type.capitalize()} alert set for {coin} {condition} {target_value:.0f}. Cooldown: {cooldown_in_hours:.0f} hours.")

@bot.slash_command(name="clear", description="Clear all alerts and/or favorites for a user")
async def clear_data(ctx, data_type: str = None):
    await ctx.defer(ephemeral=True)
    server_id = str(ctx.guild.id)  # Get the server ID
    user_id = str(ctx.author.id)

    alert_message = ""
    favorite_message = ""

    if data_type in ['alerts', None]:
        alerts = load_json_file('alerts.json')
        if server_id in alerts and user_id in alerts[server_id]:
            del alerts[server_id][user_id]
            # If no other users in the server, remove the server data too
            if not alerts[server_id]:
                del alerts[server_id]
            save_alerts(alerts, user_id, server_id, delete=True)  # Include the server ID in the save_alerts function call
            alert_message = "All alerts have been cleared."
        else:
            alert_message = "No alerts found."

    if data_type in ['favorites', None]:
        favorites = load_json_file('favorites.json')
        if server_id in favorites and user_id in favorites[server_id]:
            del favorites[server_id][user_id]
            # If no other users in the server, remove the server data too
            if not favorites[server_id]:
                del favorites[server_id]
            await save_favorites(favorites, user_id, server_id, delete=True)  # Include the server ID in the save_favorites function call
            favorite_message = "All favorites have been cleared."
        else:
            favorite_message = "No favorites found."

    # Edit the original deferred message
    if alert_message and favorite_message:
        await ctx.edit(content=f"{alert_message}\n{favorite_message}")
    else:
        await ctx.edit(content=alert_message if alert_message else favorite_message)

async def check_alerts():
    alerts = load_json_file('alerts.json')
    spam_channels = load_json_file('spam_channels.json')

    for server_id, server_alerts in alerts.items():
        for user_id, user_alerts in server_alerts.items():
            for alert in user_alerts:  # Iterate over list
                cooldown = alert.get('cooldown')  # Get the cooldown, or None if it's not present
                last_triggered = alert.get('last_triggered', 0)  # Get the last_triggered, or 0 if it's not present
                if cooldown is not None and time.time() - last_triggered < cooldown:
                    continue

                current_price = alert.get('current_price')
                if current_price is None:
                    continue  # Skip this iteration if current_price is None

                coin = alert['coin']
                channel_id = spam_channels.get(server_id, {}).get('channel_id', alert['channel_id'])
                channel = await bot.fetch_channel(int(channel_id))

                if alert['alert_type'] == 'price':
                    if (alert['condition'] == '>' and current_price > alert['target']) or \
                       (alert['condition'] == '<' and current_price < alert['target']):
                        await channel.send(f"<@{user_id}> {coin} price is now {alert['condition']} {alert['target']}")
                        alert['last_triggered'] = time.time()
                        if cooldown is None:
                            user_alerts.remove(alert)  # Remove the alert

                elif alert['alert_type'] == 'change':
                    percentage_change = alert.get('usd_24h_change')
                    if percentage_change is None:
                        continue  # Skip this iteration if percentage_change is None

                    if abs(percentage_change) > alert['target']:
                        change_type = "up" if percentage_change > 0 else "down"
                        await channel.send(f"<@{user_id}> {coin} is {change_type} {abs(round(percentage_change,1))}% in the last 24h")
                        alert['last_triggered'] = time.time()
                        if cooldown is None:
                            user_alerts.remove(alert)  # Remove the alert

    # Save the alerts
    with open('alerts.json', 'w') as f:
        json.dump(alerts, f)

@bot.slash_command(name="set_spam_channel", description="Set the current channel as the server's spam channel")
@commands.has_permissions(manage_channels=True)
async def set_spam_channel(ctx, force_all_messages: bool = False, ephemeral_messages: bool = False):
    ctx.defer(ephemeral=True)
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

    await ctx.edit(content=f"Spam channel set to {ctx.channel.name}.")
        
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
        await check_alerts()
    

    if change >= 0:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬈{change}%"))
    elif change > -10:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} ⬊{change}%"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"${price_btc} (:skull_crossbones: ⬊{change}% :skull_crossbones:)"))


bot.run(token)


