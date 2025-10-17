import discord
from discord import app_commands
from discord.ext import commands
import requests
import os

TOKEN = os.getenv("DISCORD_TOKEN")  # set this on Railway

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)

def get_binance_prices(coin, limit=90):
    symbol = f"{coin.upper()}USDT"  # automatically add USDT
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    # Return list of close prices
    prices = [float(item[4]) for item in data]  # index 4 = close price
    return prices

@bot.tree.command(name="getcoin", description="Get last 90 days stats and entry/exit info")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    values = get_binance_prices(coin)
    if not values:
        await interaction.followup.send("❌ Error fetching data. Make sure the coin exists on Binance.")
        return

    lowest = min(values)
    highest = max(values)
    avg_low = sum(sorted(values)[:max(1,int(len(values)*0.1))]) / max(1,int(len(values)*0.1))
    avg_high = sum(sorted(values)[-max(1,int(len(values)*0.1)):]) / max(1,int(len(values)*0.1))

    # Entry, Exit, Stop-loss
    buy_price = lowest * 1.2       # suggested buy zone
    sell_price = highest * 0.8     # suggested sell zone
    stop_loss = lowest              # suggested stop-loss
    feed_price = (buy_price + stop_loss) / 2  # average point between buy and stop

    # Build compact embed
    embed = discord.Embed(
        title=f"{coin.upper()} - 90 Day Summary",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📊 Prices",
        value=f"Lowest: ${lowest:.2f} | Average: ${avg_low:.2f} | Highest: ${highest:.2f}",
        inline=False
    )
    embed.add_field(
        name="💰 Signals",
        value=f"Buy: ${buy_price:.2f} | Sell: ${sell_price:.2f} | Stop: ${stop_loss:.2f} | Feed: ${feed_price:.2f}",
        inline=False
    )
    embed.set_footer(text="Last 90 days data from Binance")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)