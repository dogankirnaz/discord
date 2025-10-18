import discord
from discord import app_commands
from discord.ext import commands
import requests
import os

TOKEN = os.getenv("DISCORD_TOKEN")  # set this on Railway

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def get_binance_prices(coin, limit=90):
    symbol = f"{coin.upper()}USDT"
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    prices = [float(item[4]) for item in data]  # close prices
    return prices

def get_latest_price(coin):
    symbol = f"{coin.upper()}USDT"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    r = requests.get(url, timeout=5)
    if r.status_code != 200:
        return None
    return float(r.json()["price"])

def weighted_stats(last30, last60, last90):
    w30, w60, w90 = 0.55, 0.30, 0.15

    def weighted_avg(func):
        v30 = func(last30)
        v60 = func(last60)
        v90 = func(last90)
        return (v30 * w30) + (v60 * w60) + (v90 * w90)

    lowest = weighted_avg(min)
    highest = weighted_avg(max)
    avg_low = weighted_avg(lambda p: sum(v for v in p if v < (sum(p)/len(p))) / max(1, len([v for v in p if v < (sum(p)/len(p))])))
    avg_high = weighted_avg(lambda p: sum(v for v in p if v > (sum(p)/len(p))) / max(1, len([v for v in p if v > (sum(p)/len(p))])))
    overall_avg = weighted_avg(lambda p: sum(p) / len(p))

    buy_price = avg_low * 1.05
    sell_price = avg_high * 0.95
    stop_loss = lowest
    feed_price = (buy_price + stop_loss) / 2

    return {
        "lowest": lowest,
        "avg_low": avg_low,
        "overall_avg": overall_avg,
        "avg_high": avg_high,
        "highest": highest,
        "buy": buy_price,
        "sell": sell_price,
        "stop": stop_loss,
        "feed": feed_price
    }

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("🔁 Slash commands synced")
    except Exception as e:
        print("Sync error:", e)

@bot.tree.command(name="getcoin", description="Get weighted stats from 30/60/90 days (55/30/15%)")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    values = get_binance_prices(coin)
    latest_price = get_latest_price(coin)

    if not values or len(values) < 90 or not latest_price:
        await interaction.followup.send("Error fetching data. Make sure the coin exists on Binance and has enough history.")
        return

    last30 = values[-30:]
    last60 = values[-60:]
    last90 = values[-90:]

    stats = weighted_stats(last30, last60, last90)

    # Round values to one decimal
    for k in stats:
        stats[k] = round(stats[k], 1)

    # Determine signal based on 20% closeness
    buy_threshold = stats["buy"] * 1.2
    sell_threshold = stats["sell"] * 0.8

    if latest_price <= buy_threshold:
        signal = "BUY"
        color = discord.Color.green()
    elif latest_price >= sell_threshold:
        signal = "SELL"
        color = discord.Color.red()
    else:
        signal = "HOLD"
        color = discord.Color.greyple()

    embed = discord.Embed(
        title=f"{coin.upper()} - {signal} ({latest_price})",
        color=color
    )

    embed.add_field(
        name="Prices",
        value=f"Lowest: ${stats['avg_low']} | Average: ${stats['overall_avg']} | Highest: ${stats['avg_high']}",
        inline=False
    )

    embed.add_field(
        name="Signals",
        value=f"Buy: **${stats['buy']}** • Sell: **${stats['sell']}** • Stop: **${stats['stop']}** • Feed: **${stats['feed']}**",
        inline=False
    )

    embed.add_field(
        name="Current",
        value=f"${latest_price}",
        inline=False
    )

    embed.set_footer(text="Weights: 55% last30 | 30% last60 | 15% last90 — Data from Binance")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)