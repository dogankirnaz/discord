import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
import re
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Binance API helpers ---
def get_binance_prices(coin, limit=90):
    try:
        r = requests.get(
            f"https://api.binance.com/api/v3/klines?symbol={coin.upper()}USDT&interval=1d&limit={limit}",
            timeout=10
        )
        r.raise_for_status()
        return [float(item[4]) for item in r.json()]
    except Exception as e:
        print(f"Error fetching historical prices for {coin}: {e}")
        return None

def get_latest_price(coin):
    try:
        r = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin.upper()}USDT",
            timeout=5
        )
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:
        print(f"Error fetching latest price for {coin}: {e}")
        return None

# --- Weighted stats calculation ---
def weighted_stats(last30, last60, last90):
    w30, w60, w90 = 0.55, 0.30, 0.15

    # Helper to calculate average of a list
    def avg(lst):
        return sum(lst) / len(lst)

    # Calculate average lowest, average highest, and overall average
    lowest = w30 * avg(last30) + w60 * avg(last60) + w90 * avg(last90)
    highest = w30 * avg(last30) + w60 * avg(last60) + w90 * avg(last90)  # same here
    average = (avg(last30) + avg(last60) + avg(last90)) / 3

    buy = lowest * 1.05
    sell = highest * 0.95
    stop = lowest * 0.95

    return {
        "lowest": lowest,
        "average": average,
        "highest": highest,
        "buy": buy,
        "sell": sell,
        "stop": stop
    }

# --- Utility functions ---
def usd(value):
    return f"${value:,.2f}"

def make_signal_range(value, min_value, max_value, percent=0.1):
    low = max(value * (1 - percent), min_value)
    high = min(value * (1 + percent), max_value)
    return f"{usd(low)} - {usd(high)}"

# --- Bot events ---
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

# --- Slash command ---
@bot.tree.command(name="coin", description="Get weighted stats from 30/60/90 days (55/30/15%)")
async def coin_slash(interaction: discord.Interaction, coin: str):
    await run_coin_command(interaction=interaction, coin=coin, ephemeral=True)

# --- Shared logic ---
async def run_coin_command(interaction=None, message=None, coin=None, ephemeral=False):
    values = get_binance_prices(coin)
    latest = get_latest_price(coin)

    if not values or len(values) < 90 or not latest:
        msg = "Error fetching data. Make sure the coin exists on Binance and has enough history."
        if interaction:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        elif message:
            reply = await message.reply(msg, mention_author=True)
            await asyncio.sleep(30)
            try: 
                await message.delete()
            except: 
                pass
        return

    last30, last60, last90 = values[-30:], values[-60:], values[-90:]
    stats = weighted_stats(last30, last60, last90)

    for k in stats:
        stats[k] = round(stats[k], 2)

    buy_range = make_signal_range(stats["buy"], stats["buy"] * 0.95, stats["buy"] * 1.05)
    sell_range = make_signal_range(stats["sell"], stats["sell"] * 0.95, stats["sell"] * 1.05)
    stop_range = make_signal_range(stats["stop"], stats["lowest"] * 0.95, stats["lowest"] * 1.05)

    if stats["buy"] * 0.8 <= latest <= stats["buy"] * 1.2:
        signal, color = "BUY", discord.Color.green()
    elif stats["sell"] * 0.8 <= latest <= stats["sell"] * 1.2:
        signal, color = "SELL", discord.Color.red()
    else:
        signal, color = "HOLD", discord.Color.greyple()

    embed = discord.Embed(title=f"{coin.upper()} — {signal} ({usd(latest)})", color=color)
    embed.add_field(
        name="Prices",
        value=f"Lowest: **{usd(stats['lowest'])}** • Average: **{usd(stats['average'])}** • Highest: **{usd(stats['highest'])}**",
        inline=False
    )
    embed.add_field(
        name="Signals",
        value=f"Buy: **{buy_range}** • Sell: **{sell_range}** • Stop: **{stop_range}**",
        inline=False
    )

    if interaction:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    elif message:
        await message.reply(embed=embed, mention_author=True)
        await asyncio.sleep(30)
        try: 
            await message.delete()
        except: 
            pass

# --- Message command listener ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    match = re.match(r"!(\w+)", message.content)
    if match:
        coin_name = match.group(1)
        await run_coin_command(message=message, coin=coin_name)

bot.run(TOKEN)