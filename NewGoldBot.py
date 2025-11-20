import os, json, discord
from discord.ext import tasks
from dotenv import load_dotenv
from utils import format_price_display

load_dotenv()

intents = discord.Intents.default()
intents.presences = True
intents.guilds = True
bot = discord.Bot(intents=intents)

SEP1 = "\u2003"  # EM space
SEP2 = "\u2002"  # EN space

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

DATA_FILE = os.environ.get(
    "DATA_FILE",
    os.path.join(os.path.dirname(__file__), "crypto_data.json")
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    update_activity.start()

@tasks.loop(minutes=1)
async def update_activity():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)

        gold = d.get("gold", {})
        price = to_float(gold.get("price", 0))
        change = to_float(gold.get("change", 0))
        ratio = to_float(gold.get("sp500_ratio", 0))

        icon = move_icon(change)
        price_str = format_price_display(price, decimals=0)
        status = f"${price_str}{SEP1}{icon}{abs(change):.2f}%{SEP1}📈{ratio:.3f}"
        await bot.change_presence(activity=discord.Game(name=status[:128]))
    except Exception as e:
        print(f"update_activity error: {e}")
        await bot.change_presence(activity=discord.Game(name="Gold: Error"))

token = os.environ.get("GOLD_BOT_SECRET")
if not token:
    raise RuntimeError("GOLD_BOT_SECRET not set")
bot.run(token)
