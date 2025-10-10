import discord

# ---------- Options ----------
GAMES = [
    "Minecraft", "League of Legends", "Valorant", "Apex Legends",
    "Fortnite", "CS:GO", "Roblox", "Overwatch"
]

TIMEZONES = [f"UTC{+i}" for i in range(-12, 15)]  # UTC-12 to UTC+14

PREFERENCES = [
    "No Microphone", "Ranked Games Only", "Casual Games Only", "Streamer Friendly"
]

MAX_OPTIONS = 25  # Discord select menu max

# ---------- Modals ----------
class ProfileModal(discord.ui.Modal, title="Save Your Profile"):
    nickname = discord.ui.TextInput(
        label="Your Discord Nickname",
        placeholder="Enter a nickname",
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, games, timezone, preferences):
        super().__init__()
        self.games = games
        self.timezone = timezone
        self.preferences = preferences

    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.nickname.value or "Anonymous"
        print(f"{interaction.user} profile saved: {nickname}, Games: {self.games}, TZ: {self.timezone}, Prefs: {self.preferences}")
        await interaction.response.send_message(
            f"Profile saved!\nNickname: {nickname}\nGames: {', '.join(self.games)}\nTimezone: {self.timezone}\nPreferences: {', '.join(self.preferences)}",
            ephemeral=True
        )

# ---------- Views ----------
class PreferenceSelect(discord.ui.View):
    def __init__(self, user, games, timezone):
        super().__init__(timeout=60)
        self.user = user
        self.games = games
        self.timezone = timezone
        self.selected_preferences = []

    @discord.ui.select(
        placeholder="Select your preferences...",
        min_values=0,
        max_values=min(len(PREFERENCES), MAX_OPTIONS),
        options=[discord.SelectOption(label=pref) for pref in PREFERENCES[:MAX_OPTIONS]]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_preferences = select.values or []
        await interaction.response.send_modal(ProfileModal(self.games, self.timezone, self.selected_preferences))

class TimezoneSelect(discord.ui.View):
    def __init__(self, user, games):
        super().__init__(timeout=60)
        self.user = user
        self.games = games
        self.selected_timezone = None

    @discord.ui.select(
        placeholder="Select your timezone...",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=tz) for tz in TIMEZONES[:MAX_OPTIONS]]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_timezone = select.values[0]
        await interaction.response.send_message(
            "Now choose your preferences:",
            view=PreferenceSelect(self.user, self.games, self.selected_timezone),
            ephemeral=True
        )

class GameSelect(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.selected_games = []

    @discord.ui.select(
        placeholder="Choose your games...",
        min_values=1,
        max_values=min(len(GAMES), MAX_OPTIONS),
        options=[discord.SelectOption(label=game) for game in GAMES[:MAX_OPTIONS]]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_games = select.values
        await interaction.response.send_message(
            "Select your timezone:",
            view=TimezoneSelect(self.user, self.selected_games),
            ephemeral=True
        )

# ---------- Command ----------
async def profile_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Select your games:",
        view=GameSelect(interaction.user),
        ephemeral=True
    )