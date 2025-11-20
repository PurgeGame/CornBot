import os, json, discord
from discord.ext import tasks
from dotenv import load_dotenv
from utils import format_price_display

load_dotenv()

intents = discord.Intents.default()
intents.presences = True
intents.guilds = True
bot = discord.Bot(intents=intents)

SEP1 = "\u2003"
SEP2 = "\u2002"

def to_float(x, default=0.0):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return float(default)

def move_icon(pct: float) -> str:
    x = abs(pct)
    if x < 3:   return "⬈" if pct >= 0 else "⬊"
    if x < 6:   return "⏫" if pct >= 0 else "🔻"
    if x < 10:  return "🚀" if pct >= 0 else "💀"
    return "🌕" if pct >= 0 else "🪦"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    update_activity.start()

@tasks.loop(minutes=1)
async def update_activity():
    try:
        with open("crypto_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)["eth"]

        price_val = to_float(data.get("price", 0))
        price_str = format_price_display(price_val, decimals=0)

        change = to_float(data.get("change", 0))
        btc_ratio = to_float(data.get("btc_ratio", 0))

        icon = move_icon(change)
        ratio_trim = f"{btc_ratio:.5f}"[1:]

        status = f"${price_str}{SEP1}{icon}{abs(change):.2f}%{SEP1}🌽{ratio_trim}"
        await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print(f"update_activity error: {e}")
        await bot.change_presence(activity=discord.Game(name="ETH: Error"))

token = os.environ.get("ETH_BOT_SECRET")
if not token:
    raise RuntimeError("ETH_BOT_SECRET not set")
bot.run(token)
