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

@bot.tree.command(name="getcoin", description="Get last 90 days stats and entry/exit info")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=90"
    r = requests.get(url)

    if r.status_code != 200:
        await interaction.followup.send("❌ Error fetching data. Check the coin name.")
        return

    data = r.json()
    prices = data["prices"]

    # Extract price values only
    values = [p[1] for p in prices]

    # Find lowest and highest prices
    lowest = min(values)
    highest = max(values)

    # Average lowest and highest
    avg_low = sum(sorted(values)[:int(len(values)*0.1)]) / (len(values)*0.1)
    avg_high = sum(sorted(values)[-int(len(values)*0.1):]) / (len(values)*0.1)

    # Entry and Exit prices (20% range logic)
    entry_price = lowest * 1.2  # 20% higher than lowest
    exit_price = highest * 0.8  # 20% lower than highest
    stop_loss = lowest * 0.95   # 5% below lowest (optional safe point)

    # Find timestamps near entry and exit prices
    def find_time(target):
        closest = min(prices, key=lambda x: abs(x[1] - target))
        ts = datetime.utcfromtimestamp(closest[0] / 1000).strftime("%Y-%m-%d")
        return ts

    entry_time = find_time(entry_price)
    exit_time = find_time(exit_price)

    # Build embed message
    embed = discord.Embed(
        title=f"{coin.capitalize()} - 90 Day Summary",
        color=discord.Color.blue(),
    )
    embed.add_field(name="📉 Lowest", value=f"${lowest:.2f}", inline=True)
    embed.add_field(name="📈 Highest", value=f"${highest:.2f}", inline=True)
    embed.add_field(name="📊 Avg Low", value=f"${avg_low:.2f}", inline=True)
    embed.add_field(name="📊 Avg High", value=f"${avg_high:.2f}", inline=True)
    embed.add_field(name="🟢 Entry Point", value=f"${entry_price:.2f}\n({entry_time})", inline=False)
    embed.add_field(name="🔴 Exit Point", value=f"${exit_price:.2f}\n({exit_time})", inline=False)
    embed.add_field(name="⚠️ Stop Loss", value=f"${stop_loss:.2f}", inline=False)
    embed.set_footer(text="Data from CoinGecko • Last 90 days")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)