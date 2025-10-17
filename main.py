import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
from datetime import datetime

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

def get_binance_prices(symbol="CAKEUSDT", limit=90):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval=1d&limit={limit}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    # Convert to (timestamp, close price) format like CoinGecko
    prices = [[item[0], float(item[4])] for item in data]  # index 4 = close price
    return prices

@bot.tree.command(name="getcoin", description="Get last 90 days stats and entry/exit info")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    # Handle special case for CAKE
    if coin.lower() == "cake":
        symbol = "CAKEUSDT"
    else:
        symbol = f"{coin.upper()}USDT"

    prices = get_binance_prices(symbol=symbol, limit=90)
    if not prices:
        await interaction.followup.send("❌ Error fetching data. Check the coin symbol.")
        return

    # Extract close prices only
    values = [p[1] for p in prices]

    # Find lowest and highest prices
    lowest = min(values)
    highest = max(values)

    # Average lowest and highest (bottom/top 10%)
    avg_low = sum(sorted(values)[:int(len(values)*0.1)]) / max(1,int(len(values)*0.1))
    avg_high = sum(sorted(values)[-int(len(values)*0.1):]) / max(1,int(len(values)*0.1))

    # Entry and Exit prices (20% range logic)
    entry_price = lowest * 1.2
    exit_price = highest * 0.8
    stop_loss = lowest * 0.95

    # Find timestamps near entry and exit prices
    def find_time(target):
        closest = min(prices, key=lambda x: abs(x[1] - target))
        ts = datetime.utcfromtimestamp(closest[0]/1000).strftime("%Y-%m-%d")
        return ts

    entry_time = find_time(entry_price)
    exit_time = find_time(exit_price)

    # Build embed message
    embed = discord.Embed(
        title=f"{coin.upper()} - 90 Day Summary",
        color=discord.Color.blue(),
    )
    embed.add_field(name="📉 Lowest", value=f"${lowest:.2f}", inline=True)
    embed.add_field(name="📈 Highest", value=f"${highest:.2f}", inline=True)
    embed.add_field(name="📊 Avg Low", value=f"${avg_low:.2f}", inline=True)
    embed.add_field(name="📊 Avg High", value=f"${avg_high:.2f}", inline=True)
    embed.add_field(name="🟢 Entry Point", value=f"${entry_price:.2f}\n({entry_time})", inline=False)
    embed.add_field(name="🔴 Exit Point", value=f"${exit_price:.2f}\n({exit_time})", inline=False)
    embed.add_field(name="⚠️ Stop Loss", value=f"${stop_loss:.2f}", inline=False)
    embed.set_footer(text="Data from Binance • Last 90 days")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)