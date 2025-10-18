import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import os
import re
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_binance_prices(coin, limit=90):
    symbol = f"{coin.upper()}USDT"
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    prices = [float(item[4]) for item in data]
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
    sell_price = avg_high * 1.05  # slightly above high average
    stop_loss = lowest

    return {
        "lowest": lowest,
        "avg_low": avg_low,
        "overall_avg": overall_avg,
        "avg_high": avg_high,
        "highest": highest,
        "buy": buy_price,
        "sell": sell_price,
        "stop": stop_loss
    }

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("🔁 Slash commands synced")
    except Exception as e:
        print("Sync error:", e)

    for guild in bot.guilds:
        if guild.text_channels:
            first_channel = guild.text_channels[0]
            try:
                ready_msg = await first_channel.send("Ready!")
                print(f"✅ Sent ready message to {guild.name} in #{first_channel.name}")
                await asyncio.sleep(30)
                await ready_msg.delete()
            except Exception as e:
                print(f"⚠️ Couldn't send message in {guild.name}: {e}")

@bot.tree.command(name="coin", description="Get weighted stats from 30/60/90 days (55/30/15%)")
async def coin_slash(interaction: discord.Interaction, coin: str):
    await run_coin_command(interaction=interaction, coin=coin, ephemeral=True)

async def run_coin_command(interaction=None, message=None, coin=None, ephemeral=False):
    """Shared logic for slash commands (interaction) and message replies"""
    # Fetch data
    values = get_binance_prices(coin)
    latest_price = get_latest_price(coin)

    if not values or len(values) < 90 or not latest_price:
        msg = "Error fetching data. Make sure the coin exists on Binance and has enough history."
        if interaction:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        elif message:
            reply_msg = await message.reply(msg, mention_author=True)
            await asyncio.sleep(30)
            await reply_msg.delete()
        return

    last30 = values[-30:]
    last60 = values[-60:]
    last90 = values[-90:]

    stats = weighted_stats(last30, last60, last90)
    for k in stats:
        stats[k] = round(stats[k], 1)
    latest_price = round(latest_price, 1)

    def make_range(value, delta=0.1):
        return f"${round(value - delta, 1)} - ${round(value + delta, 1)}"

    buy_range = make_range(stats["buy"])
    sell_range = make_range(stats["sell"])
    stop_range = make_range(stats["stop"])

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
        title=f"{coin.upper()} — {signal} (${latest_price})",
        color=color
    )

    embed.add_field(
        name="Prices",
        value=(
            f"Lowest: **${stats['avg_low']}** • "
            f"Average: **${stats['overall_avg']}** • "
            f"Highest: **${stats['avg_high']}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Signals",
        value=(
            f"Buy: **{buy_range}** • "
            f"Sell: **{sell_range}** • "
            f"Stop: **{stop_range}**"
        ),
        inline=False
    )

    if interaction:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    elif message:
        reply_msg = await message.reply(embed=embed, mention_author=True)
        await asyncio.sleep(60)
        await reply_msg.delete()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    match = re.match(r"!coin\s+(\S+)", message.content)
    if match:
        coin_name = match.group(1)
        await run_coin_command(message=message, coin=coin_name)

bot.run(TOKEN)