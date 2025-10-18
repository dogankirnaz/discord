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

def sparkline(prices, length=30):
    if not prices:
        return ""
    min_p = min(prices)
    max_p = max(prices)
    blocks = "▁▂▃▄▅▆▇█"
    step = (max_p - min_p) / (len(blocks) - 1) if max_p != min_p else 1
    step_len = max(1, len(prices)//length)
    sampled = prices[::step_len][:length]
    s = ""
    for p in sampled:
        idx = int((p - min_p) / step) if step else 0
        idx = max(0, min(idx, len(blocks)-1))
        s += blocks[idx]
    return s

def calculate_stats(prices):
    overall_avg = sum(prices) / len(prices)
    high_values = [v for v in prices if v > overall_avg]
    low_values = [v for v in prices if v < overall_avg]
    avg_high = sum(high_values)/len(high_values) if high_values else overall_avg
    avg_low = sum(low_values)/len(low_values) if low_values else overall_avg
    lowest = min(prices)
    highest = max(prices)
    buy_price = avg_low * 1.05
    sell_price = avg_high * 0.95
    stop_loss = lowest
    feed_price = (buy_price + stop_loss) / 2
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

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("🔁 Slash commands synced")
    except Exception as e:
        print("Sync error:", e)

@bot.tree.command(name="getcoin", description="Weighted 90d stats (55% 30d, 30% 60d, 15% 90d)")
async def getcoin(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)

    values = get_binance_prices(coin)
    if not values or len(values) < 90:
        await interaction.followup.send("❌ Error fetching data. Need 90 days of data and a valid Binance symbol.")
        return

    # windows (most recent last)
    last_30 = values[-30:]    # most recent 30 days
    last_60 = values[-60:]    # most recent 60 days
    last_90 = values[-90:]    # most recent 90 days

    # weights as counts (deterministic merge)
    w1, w2, w3 = 55, 30, 15  # percent weights
    # build merged weighted list by repeating each list wN times
    weighted_data = (last_30 * w1) + (last_60 * w2) + (last_90 * w3)

    # calculate stats on weighted_data
    stats = calculate_stats(weighted_data)

    # also compute simple stats for each window for display (optional)
    stats_30 = calculate_stats(last_30)
    stats_60 = calculate_stats(last_60)
    stats_90 = calculate_stats(last_90)

    # sparkline for last 90
    chart = sparkline(last_90)

    # Build compact embed with ranges shown from the three windows
    embed = discord.Embed(
        title=f"{coin.upper()} - Weighted 90d Summary",
        color=discord.Color.green()
    )

    # Prices: show weighted result, and the three window lows/avg/high as ranges
    embed.add_field(
        name="📊 Prices (weighted)",
        value=f"Lowest: ${stats['avg_low']:.2f} | Average: ${stats['overall_avg']:.2f} | Highest: ${stats['avg_high']:.2f}",
        inline=False
    )

    embed.add_field(
        name="📉 Window lows / avg / highs",
        value=(
            f"30d: ${stats_30['lowest']:.2f} / ${stats_30['overall_avg']:.2f} / ${stats_30['highest']:.2f}\n"
            f"60d: ${stats_60['lowest']:.2f} / ${stats_60['overall_avg']:.2f} / ${stats_60['highest']:.2f}\n"
            f"90d: ${stats_90['lowest']:.2f} / ${stats_90['overall_avg']:.2f} / ${stats_90['highest']:.2f}"
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Signals (weighted)",
        value=(
            f"Buy: ${stats['buy']:.2f} | Sell: ${stats['sell']:.2f} | "
            f"Stop: ${stats['stop']:.2f} | Feed: ${stats['feed']:.2f}"
        ),
        inline=False
    )

    embed.add_field(
        name="📈 Trend (90d)",
        value=chart,
        inline=False
    )

    embed.set_footer(text="Weights: 55% last30 | 30% last60 | 15% last90 — Data: Binance")

    await interaction.followup.send(embed=embed)

bot.run(TOKEN)