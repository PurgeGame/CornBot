import discord
from discord.ext import tasks
import json
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    update_activity.start()

@tasks.loop(minutes=1)
async def update_activity():
    try:
        with open("crypto_data.json", "r") as f:
            data = json.load(f)["sol"]
        price, change, btc_ratio = data["price"], data["change"], data["btc_ratio"]
        if change >= 0:
            status = f"${price} ⬈{abs(change):.1f}% 🍹{f'{btc_ratio:.4f}'[1:]}"
        else:
            status = f"${price} ⬊{abs(change):.1f}% 🌽{f'{btc_ratio:.4f}'[1:]}"
        await bot.change_presence(activity=discord.Game(name=status))
    except:
        await bot.change_presence(activity=discord.Game(name="SOL: Error"))

token = os.environ.get("SOL_BOT_SECRET")
bot.run(token)