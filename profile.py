import discord

# Example game list
GAMES = [
    "Minecraft", "League of Legends", "Valorant", "Apex Legends",
    "Fortnite", "CS:GO", "Roblox", "Overwatch"
]

# ---------- Views & Modals ----------
class GameSelect(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.selected_games = []

    # Use decorator with options directly
    @discord.ui.select(
        placeholder="Choose your games...",
        min_values=1,
        max_values=len(GAMES) if GAMES else 1,
        options=[discord.SelectOption(label=game) for game in GAMES] if GAMES else [discord.SelectOption(label="No games available")],
        custom_id="game_select"
    )
    async def select_callback(self, select: discord.ui.Select, interaction: discord.Interaction):
        # Fallback in case nothing selected
        self.selected_games = select.values or ["No games selected"]
        await interaction.response.send_modal(ProfileModal(self.selected_games))


class ProfileModal(discord.ui.Modal, title="Save Your Profile"):
    def __init__(self, games):
        super().__init__()
        # Fallback in case games is empty
        self.games = games or ["No games selected"]
        self.add_item(discord.ui.InputText(
            label="Your Discord Nickname",
            placeholder="Enter a nickname"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.children[0].value or "Anonymous"
        # Save profile here
        print(f"{interaction.user} profile saved: {nickname}, Games: {self.games}")
        await interaction.response.send_message(
            f"Profile saved!\nNickname: {nickname}\nGames: {', '.join(self.games)}",
            ephemeral=True
        )


# ---------- Command Function ----------
async def profile_command(interaction: discord.Interaction):
    view = GameSelect(interaction.user)
    await interaction.response.send_message(
        "Select your games:",
        view=view,
        ephemeral=True
    )