import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
import random

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
    symbol = f"{coin.upper()}USDT"
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    prices = [float(item[4]) for item in data]  # close prices
    return prices

def calculate_stats(prices):
    overall_avg = sum(prices)/len(prices)
    high_values = [v for v in prices if v > overall_avg]
    low_values = [v for v in prices if v < overall_avg]
    avg_high = sum(high_values)/len(high_values) if high_values else overall_avg
    avg_low = sum(low_values)/len(low_values) if low_values else overall_avg
    lowest = min(prices)
    highest = max(prices)
    buy_price = avg_low * 1.05
    sell_price = avg_high * 0.95
    stop_loss = lowest
    feed_price = (buy_price + stop_loss)/2
    return {
        "avg_low": avg_low,
        "overall_avg": overall_avg,
        "avg_high": avg_high,
        "lowest": lowest,
        "highest": highest,
        "buy": buy_price,
        "sell": sell_price,
        "stop": stop_loss,
        "feed": feed_price
    }

@bot.tree.command(name="getcoin", description="Get weighted 90-day stats (55% last 30d, 30% mid, 15% early)")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    values = get_binance_prices(coin)
    if not values or len(values) < 90:
        await interaction.followup.send("❌ Error fetching data. Make sure the coin exists on Binance and has enough historical data.")
        return

    # Split the data
    last_30 = values[-30:]      # most recent month
    mid_30 = values[-60:-30]    # 31–60 days ago
    early_30 = values[-90:-60]  # 61–90 days ago

    # Apply weighted sampling
    weighted_data = (
        random.choices(last_30, k=int(len(values) * 0.55)) +
        random.choices(mid_30, k=int(len(values) * 0.30)) +
        random.choices(early_30, k=int(len(values) * 0.15))
    )

    # Calculate stats based on merged weighted data
    stats = calculate_stats(weighted_data)

    # Build embed
    embed = discord.Embed(
        title=f"{coin.upper()} - 90 Day Weighted Summary",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📊 Prices",
        value=(
            f"Lowest: ${stats['avg_low']:.2f} | "
            f"Average: ${stats['overall_avg']:.2f} | "
            f"Highest: ${stats['avg_high']:.2f}"
        ),
        inline=False
    )
    embed.add_field(
        name="💰 Signals",
        value=(
            f"Buy: ${stats['buy']:.2f} | "
            f"Sell: ${stats['sell']:.2f} | "
            f"Stop: ${stats['stop']:.2f} | "
            f"Feed: ${stats['feed']:.2f}"
        ),
        inline=False
    )
    embed.set_footer(text="Data from Binance • Weighted (55% recent, 30% mid, 15% early)")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)