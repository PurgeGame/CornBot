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
    print(f"We have logged in as {bot.user}")
    update_activity.start()

@tasks.loop(minutes=1)
async def update_activity():
    try:
        with open("crypto_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        sp = data["sp500"]
        btc = data["btc"]

        price_str = format_price_display(sp.get("price", 0), decimals=0)
        change_val = to_float(sp.get("change", 0))
        btc_price = to_float(btc.get("price", 0))

        sp_price_num = to_float(price_str)
        corn_ratio = (sp_price_num / btc_price) if btc_price else 0.0

        icon = move_icon(change_val)
        ratio_trim = f"{corn_ratio:.5f}"[1:]

        status = f"${price_str}{SEP1}{icon}{abs(change_val):.2f}%{SEP1}🌽{ratio_trim}"
        await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print(f"Error updating activity: {e}")
        await bot.change_presence(activity=discord.Game(name="S&P 500: Error"))

token = os.environ.get("SP500_BOT_SECRET")
if not token:
    raise RuntimeError("SP500_BOT_SECRET not set")
bot.run(token)
