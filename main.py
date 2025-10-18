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

    # Send a message to the first text channel
    for guild in bot.guilds:
        if guild.text_channels:
            first_channel = guild.text_channels[0]
            try:
                await first_channel.send(
                    f"Hi!"
                )
                print(f"✅ Sent ready message to {guild.name} in #{first_channel.name}")
            except Exception as e:
                print(f"⚠️ Couldn't send message in {guild.name}: {e}")

@bot.tree.command(name="coin", description="Get weighted stats from 30/60/90 days (55/30/15%)")
async def coin_slash(interaction: discord.Interaction, coin: str):
    await run_coin_command(interaction=interaction, coin=coin)

@bot.command(name="coin")
async def coin_prefix(ctx, coin: str):
    class DummyInteraction:
        # This mimics an interaction for shared logic
        async def response_defer(self, **_): pass
        async def followup_send(self, content=None, embed=None):
            await ctx.send(content=content, embed=embed)

    dummy = DummyInteraction()
    dummy.response = type('', (), {'defer': lambda *a, **k: None})()
    dummy.followup = type('', (), {'send': lambda _, **k: ctx.send(**k)})()
    await run_coin_command(interaction=dummy, coin=coin)

async def run_coin_command(interaction, coin):
    """Shared logic for both slash and prefix commands"""
    if hasattr(interaction, "response"):
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
    for k in stats:
        stats[k] = round(stats[k], 1)
    latest_price = round(latest_price, 1)

    def make_range(value):
        low = round(value * 0.8, 1)
        high = round(value * 1.2, 1)
        return f"${low} - ${high}"

    buy_range = make_range(stats["buy"])
    sell_range = make_range(stats["sell"])
    stop_range = make_range(stats["stop"])
    feed_range = make_range(stats["feed"])

    if stats["buy"] * 0.8 <= latest_price <= stats["buy"] * 1.2:
        signal = "BUY"
        color = discord.Color.green()
    elif stats["sell"] * 0.8 <= latest_price <= stats["sell"] * 1.2:
        signal = "SELL"
        color = discord.Color.red()
    else:
        signal = "HOLD"
        color = discord.Color.greyple()

    embed = discord.Embed(
        title=f"{coin.upper()} - {signal} (${latest_price})",
        color=color
    )

    embed.add_field(
        name="Prices",
        value=(
            f"Lowest: **${stats['avg_low']}**\n"
            f"Average: **${stats['overall_avg']}**\n"
            f"Highest: **${stats['avg_high']}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Signals",
        value=(
            f"Buy: **{buy_range}**\n"
            f"Sell: **{sell_range}**\n"
            f"Stop: **{stop_range}**\n"
            f"Feed: **{feed_range}**"
        ),
        inline=False
    )

    embed.set_footer(text="Weights: 55% last30 | 30% last60 | 15% last90 — Data from Binance")

    await interaction.followup.send(embed=embed)
    
bot.run(TOKEN)