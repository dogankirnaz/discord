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

def make_range(value):
    low = round(value * 0.8, 1)
    high = round(value * 1.2, 1)
    return f"${low} - ${high}"

def format_prices_block(stats):
    return (
        f"Lowest: ${round(stats['avg_low'],1)}\n"
        f"Average: ${round(stats['overall_avg'],1)}\n"
        f"Highest: ${round(stats['avg_high'],1)}"
    )

def format_signals_block(stats):
    return (
        f"Buy: {make_range(stats['buy'])}\n"
        f"Sell: {make_range(stats['sell'])}\n"
        f"Stop: {make_range(stats['stop'])}\n"
        f"Feed: {make_range(stats['feed'])}"
    )

async def build_embed_for_coin(coin):
    values = get_binance_prices(coin)
    latest_price = get_latest_price(coin)
    if not values or len(values) < 90 or latest_price is None:
        return None, "Error fetching data. Make sure the coin exists on Binance and has enough history."

    last30 = values[-30:]
    last60 = values[-60:]
    last90 = values[-90:]

    stats = weighted_stats(last30, last60, last90)
    # round numeric stats to 1 decimal for display
    for k in stats:
        stats[k] = round(stats[k], 1)
    latest_price = round(latest_price, 1)

    # determine main signal (20% closeness)
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
    embed.add_field(name="Prices", value=format_prices_block(stats), inline=False)
    embed.add_field(name="Signals", value=format_signals_block(stats), inline=False)
    embed.set_footer(text="Weights: 55% last30 | 30% last60 | 15% last90 — Data from Binance")
    return embed, None

# Slash command
@bot.tree.command(name="coin", description="Get weighted stats from 30/60/90 days (55/30/15%)")
async def coin_slash(interaction: discord.Interaction, coin: str):
    await interaction.response.defer(thinking=True)
    embed, err = await build_embed_for_coin(coin)
    if err:
        await interaction.followup.send(err)
        return
    await interaction.followup.send(embed=embed)

# Prefix command
@bot.command(name="coin")
async def coin_prefix(ctx: commands.Context, coin: str):
    # reply quickly then edit with embed (gives user immediate feedback)
    msg = await ctx.reply("Processing...")
    embed, err = await build_embed_for_coin(coin)
    if err:
        await msg.edit(content=err)
        return
    await msg.edit(content=None, embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced")
    except Exception as e:
        print("Sync error:", e)

    # send simple ready message to first allowed channel in each guild
    for guild in bot.guilds:
        first_channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if first_channel:
            try:
                await first_channel.send(f"Hi! Use /coin or !coin to get market stats.")
            except Exception:
                pass

bot.run(TOKEN)