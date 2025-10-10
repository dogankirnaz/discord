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

        # Safe fallback if GAMES is empty or invalid
        safe_games = [str(game) for game in GAMES if isinstance(game, str) and game.strip()] 
        if not safe_games:
            safe_games = ["No games available"]

        # Always create valid SelectOption objects
        options = [discord.SelectOption(label=game) for game in safe_games]

        # Add dropdown to the View
        self.add_item(discord.ui.Select(
            placeholder="Choose your games...",
            options=options,
            min_values=1,
            max_values=len(options),
            custom_id="game_select"
        ))

    @discord.ui.select(custom_id="game_select")
    async def select_callback(self, select, interaction: discord.Interaction):
        # Safe fallback if user somehow selects nothing
        self.selected_games = select.values or ["No games selected"]
        await interaction.response.send_modal(ProfileModal(self.selected_games))


class ProfileModal(discord.ui.Modal, title="Save Your Profile"):
    def __init__(self, games):
        super().__init__()
        self.games = games or ["No games selected"]

        # Input field for nickname
        self.add_item(discord.ui.InputText(
            label="Your Discord Nickname", 
            placeholder="Enter a nickname"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.children[0].value or "Anonymous"
        # Save profile to DB or memory here
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