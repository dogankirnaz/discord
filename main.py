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
    except:
        return None

def get_latest_price(coin):
    try:
        r = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin.upper()}USDT",
            timeout=5
        )
        r.raise_for_status()
        return float(r.json()["price"])
    except:
        return None

# --- Weighted stats calculation ---
def weighted_stats(last30, last60, last90):
    w30, w60, w90 = 0.55, 0.30, 0.15

    def weighted_avg(func):
        return func(last30) * w30 + func(last60) * w60 + func(last90) * w90

    lowest = weighted_avg(min)
    highest = weighted_avg(max)
    avg_low = weighted_avg(lambda p: sum(v for v in p if v < sum(p)/len(p)) / max(1, len([v for v in p if v < sum(p)/len(p)])))
    avg_high = weighted_avg(lambda p: sum(v for v in p if v > sum(p)/len(p)) / max(1, len([v for v in p if v > sum(p)/len(p)])))
    overall_avg = weighted_avg(lambda p: sum(p)/len(p))

    buy_price = avg_low * 1.05
    sell_price = avg_high * 1.05
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

# --- Utility: format USD with commas and 2 decimals ---
def usd(value):
    return f"${value:,.2f}"

def make_range(value):
    # Small delta for coins <10, larger for bigger coins
    if value < 10:
        delta = 0.1
    elif value < 100:
        delta = 1
    elif value < 1000:
        delta = 5
    else:
        delta = value * 0.01  # 1% for very big prices
    return f"{usd(value - delta)} - {usd(value + delta)}"

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
    latest_price = get_latest_price(coin)

    if not values or len(values) < 90 or not latest_price:
        msg = "Error fetching data. Make sure the coin exists on Binance and has enough history."
        if interaction:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        elif message:
            await message.reply(msg, mention_author=True)
            try: await message.delete()
            except: pass
        return

    last30, last60, last90 = values[-30:], values[-60:], values[-90:]
    stats = weighted_stats(last30, last60, last90)

    # Format all prices
    for k in stats:
        stats[k] = round(stats[k], 2)
    latest_price_str = usd(latest_price)
    buy_range = make_range(stats["buy"])
    sell_range = make_range(stats["sell"])
    stop_range = make_range(stats["stop"])

    # Determine signal
    if stats["buy"] * 0.8 <= latest_price <= stats["buy"] * 1.2:
        signal, color = "BUY", discord.Color.green()
    elif stats["sell"] * 0.8 <= latest_price <= stats["sell"] * 1.2:
        signal, color = "SELL", discord.Color.red()
    else:
        signal, color = "HOLD", discord.Color.greyple()

    # Build embed
    embed = discord.Embed(title=f"{coin.upper()} — {signal} ({latest_price_str})", color=color)
    embed.add_field(
        name="Prices",
        value=f"Lowest: **{usd(stats['avg_low'])}** • Average: **{usd(stats['overall_avg'])}** • Highest: **{usd(stats['avg_high'])}**",
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
        try:
            await asyncio.sleep(30)
            await message.delete()  # Delete user command after responding
        except:
            pass

# --- Message command listener for ! commands
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Match messages starting with !
    match = re.match(r"!(\w+)", message.content)
    if match:
        coin_name = match.group(1)
        await run_coin_command(message=message, coin=coin_name)

bot.run(TOKEN)