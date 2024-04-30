import os
import json
from dotenv import load_dotenv
import requests

load_dotenv()
MAGIC_EDEN_API = os.getenv("MAGIC_EDEN_API")

c = 0
responses = []
while c < 2000:
    url = f"https://api-mainnet.magiceden.dev/v2/ord/btc/runes/wallet/activities/bc1ph974u0ppyl4z6k0u9u895wwx3ztj98cahk2lklzhr4spww2pdjcq7pk6ly?offset={c}"
    headers = {"Authorization": f"Bearer {MAGIC_EDEN_API}"}
    response = requests.get(url, headers=headers)
    responses.append(json.loads(response.text))  # Parse the JSON response and add it to the list
    c += 100
    print(response.text)

# Join all the responses together
all_responses = sum(responses, [])

# Print all responses

with open('myactivity.json', 'w') as f:
    json.dump(all_responses, f)