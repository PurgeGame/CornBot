import discord
import sqlite3
import os,time
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.members =True
client = discord.Client(intents=intents)

token = os.environ.get("DISCORD_BOT_SECRET")
client.run(token)