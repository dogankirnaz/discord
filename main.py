import os
import discord
from discord.ext import commands
from discord import app_commands

# VARIABLES
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER = int(os.getenv("SERVER_ID"))

#BOT
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

#GLOBAL

# EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        guild = discord.Object(id=SERVER)

        # Sync test server
        guild_synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(guild_synced)} command(s) to the guild.")

        # Sync globally
        global_synced = await bot.tree.sync()
        print(f"Synced {len(global_synced)} global slash command(s).")

    except Exception as e:
        print(e)
        
# COMMANDS
@bot.tree.command(name="hello", description="Say hello!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hi, {interaction.user.mention}!", 
        ephemeral=True
    )

bot.run(TOKEN)