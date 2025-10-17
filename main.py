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

def get_binance_prices(coin, limit=60):
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

@bot.tree.command(name="getcoin", description="Get 60 days stats and buy/sell info")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    values = get_binance_prices(coin)
    if not values or len(values) < 60:
        await interaction.followup.send("❌ Error fetching data. Make sure the coin exists on Binance and has enough historical data.")
        return

    # Split first 30 and last 30 days
    first_30 = values[:30]
    last_30 = values[30:]

    stats_first = calculate_stats(first_30)
    stats_last = calculate_stats(last_30)

    # Build compact embed with ranges
    embed = discord.Embed(
        title=f"{coin.upper()} - 60 Day Summary (30/60 Days Range)",
        color=discord.Color.green()
    )
    # Prices ranges
    embed.add_field(
        name=" Prices",
        value=(
            f"Lowest: ${stats_first['lowest']:.2f} - ${stats_last['lowest']:.2f} | "
            f"Average: ${stats_first['overall_avg']:.2f} - ${stats_last['overall_avg']:.2f} | "
            f"Highest: ${stats_first['highest']:.2f} - ${stats_last['highest']:.2f}"
        ),
        inline=False
    )
    # Signals ranges
    embed.add_field(
        name=" Signals",
        value=(
            f"Buy: ${stats_first['buy']:.2f} - ${stats_last['buy']:.2f} | "
            f"Sell: ${stats_first['sell']:.2f} - ${stats_last['sell']:.2f} | "
            f"Stop: ${stats_first['stop']:.2f} - ${stats_last['stop']:.2f} | "
            f"Feed: ${stats_first['feed']:.2f} - ${stats_last['feed']:.2f}"
        ),
        inline=False
    )
    embed.set_footer(text="Data from Binance - first 30 vs last 30 days")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)