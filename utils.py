import math
import json
import os
import datetime

def is_number(n):
    try:
        float(n)
        return True
    except ValueError:
        return False
def is_integer(n):
    return isinstance(n, int)

def round_sig(num, sig_figs = 2):
    if num != 0:
        return round(num, -int(math.floor(math.log10(abs(num))) - (sig_figs - 1)))
    else:
        return 0  # Can't take the log of 0
def convert_to_float(value):
    multiplier = 1
    if 'K' in value:
        multiplier = 1e3
        value = value.replace('K', '')
    elif 'M' in value:
        multiplier = 1e6
        value = value.replace('M', '')
    elif 'B' in value:
        multiplier = 1e9
        value = value.replace('B', '')
    return float(value) * multiplier



def format_number(num, integer=False,bitcoin = False):
    if num is None or not is_number(num):
        return 0
    else:
        num = float(num)
        if num % 1 == 0:  # check if the decimal part is zero
            num = int(num)
        if num >= 1e10:
            return f'{num/1e9:,.0f} B'
        elif num >= 1e6:
            return f'{num/1e6:,.0f} M'
        elif num >= 1e4 and bitcoin == False:
            return f'{num/1000:,.0f} K'
        elif num >= 1e3:
            return f'{int(num):,}'
        elif num >= 1:
            if num % 1 == 0 or integer==True:
                return int(num)
            return f'{num:.2f}'
        elif num == 0:
            return 0
        elif num < 0.01:
            return f'{num:.2e}'
        elif num > .01:
            return f'{num:.2f}'
        else:
            return round_sig(num, 2)
        
def format_number_with_symbol(num, symbol,integer=False):
        formatted_number = str(format_number(num,integer))
        if symbol == 'USD':
            return f'${formatted_number}'
        return f'{formatted_number} {symbol}'
        
def is_rune(coin_id):
    if is_all_caps(coin_id) or "•" in coin_id:
        return True
    
def sanitize_rune(rune):
    return rune.replace('•', '')

def is_all_caps(s):
    return all(c.isupper() for c in s if c.isalpha())

def check_coin_quantity(user_id, coin):
    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    if user_id in user_data and 'runes' in user_data[user_id] and coin in user_data[user_id]['runes']:
        return user_data[user_id]['runes'][coin]
    else:
        return None
    
def truncate_name(name, max_length=15):
    if len(name) > max_length:
        name = sanitize_rune(name)
    return name[:max_length-2] + '..' if len(name) > max_length else name

def format_change(change):
    if change is None:
        return 'N/A'
    return f"{'+-'[change < 0]}{abs(change):.1f}%"

async def split_table(table, limit=2000):
    messages = []
    current_message = ""
    for line in str(table).split('\n'):
        if len(current_message) + len(line) + len('```\n\n```') > limit:  # account for markdown code block characters
            messages.append(f'```\n{current_message}\n```')
            current_message = line
        else:
            current_message += '\n' + line
    messages.append(f'```\n{current_message}\n```')
    return messages

 
                
def add_rune_data(user_id, rune_data):
    # Load the existing data from the JSON file
    if not os.path.exists('favorite_runes.json'):
        return False

    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    # Check if the user exists
    if user_id not in user_data:
        return False

    # Add the coin data to the user's data
    user_data[user_id]['runes'][rune_data['ticker']] = {
        'balance': rune_data['formattedBalance']
    }

    # Write the updated data back to the JSON file
    with open('favorite_runes.json', 'w') as f:
        json.dump(user_data, f, indent=4)
      

def load_user_runes(user_id):
    # Check if the file exists
    if not os.path.exists('favorite_runes.json'):
        return None

    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    # Check if the user exists and has runes
    if user_id in user_data and 'runes' in user_data[user_id]:
        return user_data[user_id]['runes']

    return None

def add_or_update_user_address(user_id, address):
    # Load the existing data from the JSON file
    if not os.path.exists('favorite_runes.json'):
        user_data = {}

    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    # Add or update the user's address
    if user_id not in user_data:
        user_data[user_id] = {'address': address, 'runes': {}}
    else:
        user_data[user_id]['address'] = address

    # Write the updated data back to the JSON file
    with open('favorite_runes.json', 'w') as f:
        json.dump(user_data, f, indent=4)
    

def get_user_data(user_id):
    # Load the data from the JSON file
    with open('favorite_runes.json', 'r') as f:
        user_data = json.load(f)

    # Get the data for the specified user
    if user_id in user_data:
        return user_data[user_id]
    else:
        return None


def user_rune_balances(user_id, address, coins_quantities):
    # Create a dictionary with the user data
    user_data = {
        user_id: {
            "address": address,
            "coins": coins_quantities
        }
    }

    # Write the dictionary to a JSON file
    with open('favorite_runes.json', 'w') as f:
        json.dump(user_data, f, indent=4)

def load_favorites(type='coins'):
    filename = 'favorite_coins.json' if type == 'coins' else 'favorite_runes.json'
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as f:
        data = json.load(f)
        return data if data is not None else {}

async def save_favorites(favorites, type='coins'):
    filename = 'favorite_coins.json' if type == 'coins' else 'favorite_runes.json'
    with open(filename, 'w') as f:
        json.dump(favorites, f)


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

