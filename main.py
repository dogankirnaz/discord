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

    # Flatten lists for each weighted period
    all_values = last30 + last60 + last90

    # Weighted average of all values
    main_average = (sum(last30)*w30 + sum(last60)*w60 + sum(last90)*w90) / (len(last30)*w30 + len(last60)*w60 + len(last90)*w90)

    # Collect values lower and higher than average
    lows = [v for v in all_values if v < main_average]
    highs = [v for v in all_values if v > main_average]

    # Midpoint (average) of lows and highs
    lowest = sum(lows)/len(lows) if lows else main_average
    highest = sum(highs)/len(highs) if highs else main_average
    average = max((lowest + highest) / 2, 0)
    
    # Calculate buy/sell/stop
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

# Dynamic signal range based on value magnitude
def make_signal_range(value, percent=0.01):  # 0.1%
    delta = value * percent
    low = value - delta
    high = value + delta
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

    buy_range = make_signal_range(stats["buy"])
    sell_range = make_signal_range(stats["sell"])
    stop_range = make_signal_range(stats["stop"])

    if latest <= stats["stop"] * 0.8:
        signal, color = "WAIT", discord.Color.orange()
    elif stats["buy"] * 0.9 <= latest <= stats["buy"] * 1.1:
        signal, color = "BUY", discord.Color.green()
    elif stats["sell"] * 0.9 <= latest <= stats["sell"] * 1.1:
        signal, color = "SELL", discord.Color.red()
    else:
        signal, color = "HOLD", discord.Color.greyple()

    embed = discord.Embed(title=f"{coin.upper()} — {signal} ({usd(latest)})", color=color)
    embed.add_field(
        name="Prices",
        value=f"Lowest: **{usd(stats['lowest'])}** \nAverage: **{usd(stats['average'])}** \nHighest: **{usd(stats['highest'])}**",
        inline=False
    )
    embed.add_field(
    name="Signals",
        value=f"Buy: **{buy_range}** \nSell: **{sell_range}** \nStop: **{stop_range}**",
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