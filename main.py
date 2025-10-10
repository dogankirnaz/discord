import os
import discord
from discord.ext import commands
from discord import app_commands
from profile import profile_command

# VARIABLES
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER = int(os.getenv("SERVER_ID"))

# BOT
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        guild = discord.Object(id=SERVER)
        guild_synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(guild_synced)} command(s) to the guild.")
        global_synced = await bot.tree.sync()
        print(f"Synced {len(global_synced)} global slash command(s).")
    except Exception as e:
        print(e)

# TEST COMMAND
@bot.tree.command(name="hello", description="Say hello!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hi, {interaction.user.mention}!", 
        ephemeral=True
    )

# PROFILE COMMAND
@bot.tree.command(name="profile", description="Create or update your game profile")
async def profile(interaction: discord.Interaction):
    await profile_command(interaction)

bot.run(TOKEN)