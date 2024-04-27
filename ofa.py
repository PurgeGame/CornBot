import random
from utils import *
from datetime import datetime
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

def get_all_runes(favorites):
    all_runes = []
    for user_data in favorites.values():
        all_runes += list(user_data['runes'].keys())
    return all_runes

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
        if is_rune(coin):
            await ctx.edit(content=f'Official Financial Advice: {action} {coin} {buy_time} at {format_number(buy_price)} sats, with {leverage}x leverage. {emoji}')
        else:
            await ctx.edit(content=f'Official Financial Advice: {action} {coin} {buy_time} at ${format_number(buy_price)}, with {leverage}x leverage. {emoji}')
    else:
        if is_rune(coin):
            await ctx.edit(content=f'Official Financial Advice: {action} {coin} {buy_time} at {format_number(buy_price)} sats. {emoji}')
        else:
            await ctx.edit(content=f'Official Financial Advice: {action} {coin} {buy_time} at ${format_number(buy_price)}. {emoji}')