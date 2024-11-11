import os
import json
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta, timezone
import aiohttp
import asyncio
import glob
from dateutil.parser import parse
# runes_data = {}
# all_transactions = {}
# if os.path.exists('all_transactions.json'):
#     with open('all_transactions.json', 'r') as f:
#         all_transactions = json.load(f)


# load_dotenv()
# MAGIC_EDEN_API = os.getenv("MAGIC_EDEN_API")

# def load_most_recent_json():
#     global runes_data
#     # Get a list of all JSON files in the 'historical' folder
#     files = glob.glob('historical/*.json')

#     # Sort the files by modification time
#     files.sort(key=os.path.getmtime)

#     # Get the most recent file
#     most_recent_file = files[-1]

#     # Load the data from the most recent file
#     with open(most_recent_file, 'r') as f:
#         data = json.load(f)
#     runes_data = data.get('runes_data', {})
#     return data

# load_most_recent_json()
# def get_latest_transaction_date(transactions):
#     # Parse the dates and convert them to datetime objects
#     dates = [datetime.strptime(txn['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ") for txn in transactions]

#     # Get the latest date
#     latest_date = max(dates)

#     return latest_date

# def filter_transactions(transactions, kind):
#     return [txn for txn in transactions if txn['kind'] == kind]

# async def fetch_rune_data(rune_name,type = 'price',offset = 0):
#     if type == 'transactions':
#         url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/activities/{rune_name}?offset={offset}"
#     else:
#         url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/market/{rune_name}/info"
#     headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}

#     async with aiohttp.ClientSession() as session:

#         async with session.get(url, headers=headers) as response:
#             if response.status == 200 and response.content_type == 'application/json':
#                 data = await response.json()

#                 if data:
#                     return data
#                 else:
#                     return {}
#             else:
#                 return {}
            
# def snipe_filter(rune, transactions):
#     global runes_data
#     if 'divisibility' in runes_data[rune]:
#         divisibility = int(runes_data[rune]['divisibility'])
#     else:
#         return []
#     # Get the current price of the rune
#     current_price = runes_data.get(rune, {}).get('current_price')


#     # Check if the current price is not None
#     if current_price is None:
#         print(f"No current price found for rune: {rune}")
#         return []

#     # Initialize an empty list to store the transactions where the price per unit is below the current price
#     below_current_price_transactions = []

#     # Iterate over the transactions
#     for txn in transactions:
#         # Calculate the price per unit for the transaction
#         price_per_unit = float(txn['listedPrice'])/((float(txn['amount']) / 10**divisibility))

#         # Check if the price per unit is below the current price
#         if price_per_unit < current_price * 0.95:
#             # If it is, add the transaction to the list
#             below_current_price_transactions.append(txn)

#     # Initialize an empty list to store the transactions where the total value at the new current price is more than $200
#     valuable_transactions = []

#     # Iterate over the transactions where the price per unit is below the current price
#     for txn in below_current_price_transactions:
#         # Calculate the total value at the new current price
#         total_value = float(txn['listedPrice']) * float(txn['btcUsdPrice']) / 1e8
#         # Check if the total value is more than $200
#         if total_value > 200:
#             # If it is, add the total value to the transaction data
#             total_value = int(total_value)
#             txn['total_value'] = total_value

#             # Add the transaction to the list
#             valuable_transactions.append(txn)

#     return valuable_transactions


# def snipe_check(rune, buys, sold):
#     global runes_data

#     # Create a set of the selling transactions' txIds and mempoolTxIds
#     selling_set = {txn.get('txId', '') for txn in sold}
#     selling_set.update({txn.get('mempoolTxId', '') for txn in sold})

#     # Create a dictionary of the buying transactions' mempoolTxIds
#     buying_dict = {}
#     for buy in buys:
#         mempoolTxId = buy.get('mempoolTxId', '')
#         if mempoolTxId not in buying_dict:
#             buying_dict[mempoolTxId] = buy

#     # Filter the buying transactions to get only the ones that haven't been sold and don't have duplicate mempoolTxIds
#     unsold_orders = [buy for buy in buying_dict.values() if buy.get('txId', '') not in selling_set and buy.get('mempoolTxId', '') not in selling_set]

#     # Filter out transactions that are more than an hour old
#     unsold_orders = [order for order in unsold_orders if parse(order['createdAt']).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(hours=1)]
#     snipes = snipe_filter(rune,unsold_orders)

#     return snipes




# async def secondary_check_price_change(rune):
#     global runes_data 
#     global all_transactions
#     if 'divisibility' not in runes_data[rune]:
#         return
#     else:
#         divisibility = int(runes_data[rune]['divisibility'])
#     if runes_data.get(rune,{}).get('volume_24h',0) <= 1000000:
#         return
#     c=0
#     while True:
#         new_data = await fetch_rune_data(rune,'transactions',c*100)
#         # Check if new_data is empty
#         if not new_data:
#             break
#         # Add the new transactions to the dictionary
#         all_transactions.update({txn['id']: txn for txn in new_data if datetime.now(timezone.utc) - parse(txn['createdAt']) <= timedelta(hours=2)})
#         # Check if any of the new transactions are already in the dictionary
#         if any(txn['id'] in all_transactions for txn in new_data):
#             break
#         # Check if any of the transactions are more than 2 hours old
#         if any(datetime.now(timezone.utc) - parse(txn['createdAt']) > timedelta(hours=2) for txn in new_data):
#             break
#         c+=1

# # Save the transactions to the JSON file
#     with open('all_transactions.json', 'w') as f:
#         json.dump(all_transactions, f)

#         buys = filter_transactions(all_transactions.values(), 'buying_broadcasted')

#         sold = filter_transactions(all_transactions.values(),'sent')

#         # listings = filter_transactions(all_transactions.values(),'create_sell_order')
#         # cancels = filter_transactions(all_transactions.values(),'order_cancelled')


#         # Create a set of the selling transactions

#     snipes = snipe_check(rune,buys,sold)
#     # Calculate the number of runes and the price per rune for each snipe
#     snipe_info = [
#         {
#             'txId': snipe['mempoolTxId'],
#             'total_value': snipe.get('total_value', 'N/A'),
#             'number_of_runes': float(snipe['amount']) / (10 ** divisibility),
#             'price_per_rune': float(snipe['listedPrice']) / (float(snipe['amount']) / (10 ** divisibility)) if float(snipe['amount']) != 0 else 'N/A'
#         }
#         for snipe in snipes
# ]

#     for info in snipe_info:
#         print(rune, info)

# async def main():
#     global runes_data
#     tasks = [secondary_check_price_change(rune) for rune in runes_data]
#     await asyncio.gather(*tasks)

# asyncio.run(main())















# import json

# # Load the JSON file
# with open('historical/data_2024-05-26.json') as f:
#     data = json.load(f)

# # Iterate over the runes_data dictionary
# for rune in data['runes_data']:
#     # Get the price list for the current rune
#     price_list = data['runes_data'][rune]['price_list']
#     # Convert strings to floats where possible, otherwise remove the item
#     new_price_list = []
#     for price in price_list:
#         try:
#             new_price_list.append(float(price))
#         except ValueError:
#             pass  # Do nothing if the conversion fails
#     data['runes_data'][rune]['price_list'] = new_price_list

# # Write the cleaned data back to the JSON file
# with open('historical/data_2024-05-26.json', 'w') as f:
#     json.dump(data, f)










# c = 0
# responses = []
# while c < 5:
#     url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/activities/SATOSHINAKAMOTO"
#     headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}
#     response = requests.get(url, headers=headers)
#     responses.append(json.loads(response.text))  # Parse the JSON response and add it to the list
#     c += 100
#     print(response.text)

# # Join all the responses together
# all_responses = sum(responses, [])

# # Print all responses

# with open('myactivity.json', 'w') as f:
#     json.dump(all_responses, f)