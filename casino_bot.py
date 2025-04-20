import discord
import random
import os
import json
import openpyxl
import asyncio
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from datetime import datetime, timedelta

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Enable members intent
bot = commands.Bot(command_prefix="/", intents=intents)

# File paths
BALANCES_FILE = "balances.json"
TRANSACTIONS_FILE = "transactions.json"
STAFF_CHANNEL_ID = 1358055200748998816
LOTTERY_ANNOUNCE_CHANNEL_ID = 1362495523273310218
LOTTERY_FILE = "lottery_entries.json"
TOS_LINK = "https://docs.google.com/document/d/19KVZPvkb16YrnA7qi1x0DH9kojpRHh0LzoLjcwAAzpU/edit?usp=sharing"
MAX_BET = 10000
REGISTERED_USERS_FILE = "registered_users.json"
LOTTERY_TICKET_PRICE = 100
DRAW_DAY = 6
DRAW_HOUR = 0
DRAW_MINUTE = 0

#Lottery load & Save data
def load_lottery_entries():
    if os.path.exists(LOTTERY_FILE):
        with open(LOTTERY_FILE, "r") as f:
            return json.load(f)
    return []
def save_lottery_entries(entries):
    with open(LOTTERY_FILE, "w") as f:
        json.dump(entries, f, indent=4)
lottery_entries = load_lottery_entries()


# Load and save registered users
def load_registered_users():
    if os.path.exists(REGISTERED_USERS_FILE):
        with open(REGISTERED_USERS_FILE, "r") as f:
            return json.load(f)
    return []
def save_registered_users(users):
    with open(REGISTERED_USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)
registered_users = load_registered_users()
def is_registered(user_id):
    return str(user_id) in registered_users



# Load data from file
def load_data(file_path):
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:  # Ensure file exists & has content
            with open(file_path, "r") as file:
                data = json.load(file)
                if isinstance(data, dict):  # Ensure the loaded data is a dictionary
                    return data
        print(f"⚠️ Warning: {file_path} is empty or invalid. Using default values.")
        return {}  # Return empty dictionary if the file is empty or corrupted
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"⚠️ Error loading {file_path}. Using default values.")
        return {}
def save_data(file_path, data):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


# Load environment variables from a .env file
load_dotenv()
BOT_KEY = os.getenv("BOT_TOKEN")

tree = bot.tree

# User balances and transactions
balances = load_data(BALANCES_FILE)  # Ensure it loads
transactions = load_data(TRANSACTIONS_FILE)  # Ensure it loads

# Log transactions to excel
def log_transaction_to_excel(user_id, description):
    file_name = "transaction_log.xlsx"

    # Load existing workbook or create a new one
    if os.path.exists(file_name):
        workbook = openpyxl.load_workbook(file_name)
        sheet = workbook.active
    else:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Timestamp", "User ID", "Username", "Description"])  # Header

    # Get username (fallback to Unknown)
    user = bot.get_user(int(user_id))
    username = user.name if user else "Unknown"

    # Timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append the log entry
    sheet.append([timestamp, user_id, username, description])

    # Save the file
    workbook.save(file_name)

# Log transactions for each user
def log_transaction(user_id, description):
    user_id = str(user_id)
    transactions.setdefault(user_id, []).append(description)
    save_data(TRANSACTIONS_FILE, transactions)
    log_transaction_to_excel(user_id, description)


# Helper function to get balance
def get_balance(user_id):
    user_id_str = str(user_id)  # Ensure we are checking string keys
    return balances.get(user_id_str, 0)  # Fetch using string key


# Helper function to update balance
def update_balance(user_id, amount):
    user_id_str = str(user_id)  # Convert user ID to string for consistency
    balances[user_id_str] = get_balance(user_id_str) + amount
    save_data(BALANCES_FILE, balances)


# Command to check balance
@bot.tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    user_id = interaction.user.id
    balance = get_balance(user_id)
    await interaction.response.send_message(f"💰 Your balance is `${balance}` Redmont Dollars.", ephemeral=True)


# Admin command to adjust a specific user's balance
@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="adjust_balance", description="Admins can adjust a user's balance.")
@app_commands.describe(
    member="The user whose balance you want to adjust",
    action="Increase or Decrease the balance",
    amount="Amount to adjust"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Increase", value="increase"),
        app_commands.Choice(name="Decrease", value="decrease")
    ]
)
async def adjust_balance(interaction: discord.Interaction, member: discord.Member, action: app_commands.Choice[str], amount: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 You must be an admin to use this command.", ephemeral=True)

    if amount <= 0:
        return await interaction.response.send_message("❌ Please enter a positive amount.", ephemeral=True)

    modifier = amount if action.value == "increase" else -amount

    # Update balance
    update_balance(member.id, modifier)
    new_balance = get_balance(member.id)

    # Log to transactions.json
    try:
        with open("transactions.json", "r") as f:
            transactions = json.load(f)
    except FileNotFoundError:
        transactions = {}

    user_id = str(member.id)
    if user_id not in transactions:
        transactions[user_id] = []

    transactions[user_id].append(
        f"[ADMIN] {'Increased' if modifier > 0 else 'Decreased'} ${abs(modifier)} | New Balance: ${new_balance}"
    )

    with open("transactions.json", "w") as f:
        json.dump(transactions, f, indent=4)

    await interaction.response.send_message(
        f"✅ {'Increased' if modifier > 0 else 'Decreased'} `${abs(modifier)}` from {member.mention}'s balance.\n📦 New balance: `${new_balance}`",
        ephemeral=True
    )


# Roll Dice game
@bot.tree.command(name="roll_dice", description="Roll a dice against the bot. If both rolls match, you win 3x your bet!")
async def roll_dice(interaction: discord.Interaction, bet: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"❌ Invalid bet amount! \n Bet must be between 1 and ${MAX_BET}.", ephemeral=True)
        return
    
    user_balance = get_balance(interaction.user.id)
    if bet > user_balance:
        await interaction.response.send_message("❌ You don't have enough Balance to place this bet!", ephemeral=True)
        return
    
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    if user_roll == bot_roll:
        winnings = bet * 2
        update_balance(interaction.user.id, winnings-bet)  # Net gain
        log_transaction(interaction.user.id, f"Won in roll dice +${winnings}")
        result = f"🎉 You rolled a {user_roll}, and the bot rolled a {bot_roll}. You win **${winnings}**!"
    else:
        update_balance(interaction.user.id, -bet)
        log_transaction(interaction.user.id, f"Lost in roll dice -${bet}")
        result = f"😞 You rolled a {user_roll}, and the bot rolled a {bot_roll}. You lose **${bet}**."
    
    embed = discord.Embed(title="🎲 Roll Dice 🎲", description=result, color=discord.Color.green() if user_roll == bot_roll else discord.Color.red())
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Coinflip game
@bot.tree.command(name="coinflip", description="Flip a coin and bet on heads or tails")
async def coinflip(interaction: discord.Interaction, bet: int, choice: str):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    user_id = interaction.user.id
    if choice.lower() not in ["heads", "tails"]:
        await interaction.response.send_message("⚠️ Choose either 'heads' or 'tails'!", ephemeral=True)
        return
    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"⚠️ Bet must be between 1 and {MAX_BET}!", ephemeral=True)
        return
    if bet > get_balance(user_id):
        await interaction.response.send_message("💸 You don't have enough Balance!", ephemeral=True)
        return
    
    result = random.choice(["heads", "tails"])
    embed = discord.Embed(title="🪙 Coin Flip 🪙", description=f"The coin landed on **{result}**!", color=discord.Color.orange())
    
    if result == choice.lower():
        winnings = bet * 2
        update_balance(user_id, winnings-bet)  # Net gain
        log_transaction(user_id, f"Won in coinflip +${winnings}")
        embed.add_field(name="🎉 You Win!", value=f"You won **${winnings}**!", inline=False)
    else:
        update_balance(user_id, -bet)
        log_transaction(user_id, f"Lost in coinflip -${bet}")
        embed.add_field(name="😢 You Lost", value=f"You lost **${bet}**.", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Blackjack game
class BlackjackGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.player_hand = [random.randint(1, 11), random.randint(1, 11)]
        self.bot_hand = [random.randint(1, 11), random.randint(1, 11)]
        self.game_over = False

    def hit(self):
        self.player_hand.append(random.randint(1, 11))
        if sum(self.player_hand) > 21:
            self.game_over = True
        return self.player_hand

    def stand(self):
        while sum(self.bot_hand) < 17:
            self.bot_hand.append(random.randint(1, 11))
        self.game_over = True
        return self.bot_hand

    def is_blackjack(self, hand):
        return sorted(hand) == [1, 10]

    def get_winner(self):
        if self.is_blackjack(self.player_hand):
            return "blackjack"

        player_total = sum(self.player_hand)
        bot_total = sum(self.bot_hand)

        if player_total > 21:
            return "bot"
        elif bot_total > 21 or player_total > bot_total:
            return "player"
        elif player_total < bot_total:
            return "bot"
        else:
            return "tie"

games = {}

class BlackjackView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__()
        self.user_id = user_id
        self.bet = bet

    async def end_game(self, interaction, game):
        winner = game.get_winner()
        user_id = interaction.user.id
        winnings = 0

        if winner == "blackjack":
            winnings = int(game.bet * 2.5)
            update_balance(user_id, winnings)
            log_transaction(user_id, f"Blackjack! Win: +${winnings}")
            result = f"🂡 Blackjack! 🎉 You win **${winnings}**!"
        elif winner == "player":
            winnings = game.bet * 2
            update_balance(user_id, winnings)
            log_transaction(user_id, f"Blackjack win: +${winnings}")
            result = f"🎉 You win **${winnings}**!"
        elif winner == "tie":
            update_balance(user_id, game.bet)
            log_transaction(user_id, f"Blackjack tie: ${game.bet}")
            result = f"🤝 It's a tie! Your bet of **${game.bet}** has been returned."
        else:
            log_transaction(user_id, f"Blackjack loss: -${game.bet}")
            result = f"😢 You lose **${game.bet}**. Better luck next time!"

        for item in self.children:
            item.disabled = True

        embed = discord.Embed(title="🃏 Blackjack - Game Over 🃏", color=discord.Color.gold())
        embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
        embed.add_field(name="Bot's Hand", value=f"{game.bot_hand} (Total: {sum(game.bot_hand)})", inline=False)
        embed.add_field(name="Game Result", value=result, inline=False)

        view = BlackjackPlayAgainView(self.user_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in games:
            await interaction.response.send_message("⚠️ No active blackjack game found!", ephemeral=True)
            return

        game = games[user_id]
        game.hit()

        if game.game_over:
            await self.end_game(interaction, game)
            del games[user_id]
            return

        embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
        embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
        embed.add_field(name="Bot's Hand", value=f"[{game.bot_hand[0]}, ?]", inline=False)
        embed.add_field(name="Game Status", value="Hit or Stand?", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in games:
            await interaction.response.send_message("⚠️ No active blackjack game found!", ephemeral=True)
            return

        game = games[user_id]
        game.stand()
        await self.end_game(interaction, game)
        del games[user_id]

class BlackjackPlayAgainView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__()
        self.user_id = user_id
        self.bet = bet

    @discord.ui.button(label="🔁 Play Again", style=discord.ButtonStyle.success)
    async def play_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if get_balance(self.user_id) < self.bet:
            await interaction.response.send_message("💸 You don't have enough Balance to play again!", ephemeral=True)
            return

        games[self.user_id] = BlackjackGame(self.user_id, self.bet)
        update_balance(self.user_id, -self.bet)

        game = games[self.user_id]

        embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
        embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
        embed.add_field(name="Bot's Hand", value=f"[{game.bot_hand[0]}, ?]", inline=False)
        embed.add_field(name="Game Status", value="Hit or Stand?", inline=False)

        view = BlackjackView(self.user_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

@bot.tree.command(name="blackjack", description="Play a game of blackjack against the bot")
async def blackjack(interaction: discord.Interaction, bet: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    user_id = interaction.user.id
    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"⚠️ Bet must be between 1 and {MAX_BET}!", ephemeral=True)
        return
    if bet > get_balance(user_id):
        await interaction.response.send_message("💸 You don't have enough Balance!", ephemeral=True)
        return

    games[user_id] = BlackjackGame(user_id, bet)
    update_balance(user_id, -bet)

    game = games[user_id]

    embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
    embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
    embed.add_field(name="Bot's Hand", value=f"[{game.bot_hand[0]}, ?]", inline=False)
    embed.add_field(name="Game Status", value="Hit or Stand?", inline=False)

    view = BlackjackView(user_id, bet)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



# Graceful shutdown function
def handle_shutdown():
    print("🔴 Saving data before shutdown...")
    save_data(BALANCES_FILE, balances)
    save_data(TRANSACTIONS_FILE, transactions)
    print("✅ Data saved successfully. Bot is shutting down.")


# Shutdown command for admins
@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="shutdown", description="Safely shutdown the bot (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return
    await interaction.response.send_message("🔴 Shutting down the bot safely...", ephemeral=True)
    handle_shutdown()
    await bot.close()


# Run the bot
@bot.event
async def on_ready():
    global balances, transactions  # Ensure global variables are updated

    # Load balances
    loaded_balances = load_data(BALANCES_FILE)
    if isinstance(loaded_balances, dict):
        balances.update(loaded_balances)  # Use update() instead of replacing the dict
        print("✅ Balances successfully loaded from file.")
    else:
        print("⚠️ Balances failed to load. Using default empty dictionary.")

    # Load transactions
    loaded_transactions = load_data(TRANSACTIONS_FILE)
    if isinstance(loaded_transactions, dict):
        transactions.update(loaded_transactions)
        print("✅ Transactions successfully loaded from file.")
    else:
        print("⚠️ Transactions failed to load. Using default empty dictionary.")

    await bot.tree.sync()
    print(f'✅ Logged in as {bot.user}')
    
    bot.loop.create_task(lottery_auto_draw())


#Deposit accept/reject
class DepositView(discord.ui.View):
    def __init__(self, user: discord.User, amount: int):
        super().__init__(timeout=None)
        self.user = user
        self.amount = amount

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        update_balance(self.user.id, self.amount)
        log_transaction(self.user.id, f"Deposit accepted: +${self.amount}")
        await interaction.response.edit_message(content=f"✅ Deposit of ${self.amount} accepted for {self.user.mention}.", view=None)
        await self.user.send(f"✅ Your deposit of ${self.amount} has been **accepted**!")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ Deposit of ${self.amount} rejected for {self.user.mention}.", view=None)
        await self.user.send(f"❌ Your deposit of ${self.amount} has been **rejected**.")

@bot.tree.command(name="deposit", description="Submit a deposit request with proof")
@app_commands.describe(amount="Amount to deposit", proof="Upload a screenshot as proof")
async def deposit(interaction: discord.Interaction, amount: int, proof: discord.Attachment):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("⚠️ Amount must be positive!", ephemeral=True)
        return

    embed = discord.Embed(title="💰 Deposit Request", color=discord.Color.gold())
    embed.add_field(name="User", value=interaction.user.mention, inline=False)
    embed.add_field(name="Amount", value=f"${amount}", inline=False)
    embed.set_image(url=proof.url)

    staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
    await staff_channel.send(embed=embed, view=DepositView(interaction.user, amount))

    await interaction.response.send_message("✅ Your deposit request has been submitted for review.", ephemeral=True)


#Withdrawal accept/reject
class WithdrawalView(discord.ui.View):
    def __init__(self, user: discord.User, amount: int, ign: str):
        super().__init__(timeout=None)
        self.user = user
        self.amount = amount
        self.ign = ign

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        update_balance(self.user.id, -self.amount)
        log_transaction(self.user.id, f"Withdrawal accepted: -${self.amount}")
        await interaction.response.edit_message(content=f"✅ Withdrawal of ${self.amount} approved for {self.user.mention}.", view=None)
        await self.user.send(f"✅ Your withdrawal of ${self.amount} has been **approved**!\nIn-game name: `{self.ign}`")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ Withdrawal of ${self.amount} rejected for {self.user.mention}.", view=None)
        await self.user.send(f"❌ Your withdrawal of ${self.amount} has been **rejected**.")

@bot.tree.command(name="withdraw", description="Submit a withdrawal request")
@app_commands.describe(amount="Amount to withdraw", ign="Your in-game name")
async def withdraw(interaction: discord.Interaction, amount: int, ign: str):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)  # ✅ lets the bot "think" longer

    if amount <= 0:
        await interaction.followup.send("⚠️ Amount must be positive!", ephemeral=True)
        return

    balance = get_balance(interaction.user.id)

    if balance < amount:
        await interaction.followup.send("❌ You don't have enough Balance.", ephemeral=True)
        return

    embed = discord.Embed(title="🏦 Withdrawal Request", color=discord.Color.red())
    embed.add_field(name="User", value=interaction.user.mention, inline=False)
    embed.add_field(name="Amount", value=f"${amount}", inline=False)
    embed.add_field(name="IGN", value=ign, inline=False)

    staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
    await staff_channel.send(embed=embed, view=WithdrawalView(interaction.user, amount, ign))

    await interaction.followup.send("✅ Your withdrawal request has been submitted for review.", ephemeral=True)


#Slots games
EMOJIS = ["🍒", "🍋", "🍉", "⭐", "🔔", "🍇"]
class SlotsView(discord.ui.View):
    def __init__(self, user: discord.User, bet: int, multiplier: float, message: discord.Message):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.multiplier = multiplier
        self.message = message

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("⚠️ This button isn't for you!", ephemeral=True)
            return

        balance = get_balance(self.user.id)
        if balance < self.bet:
            await interaction.response.send_message("❌ Not enough Balance to play again.", ephemeral=True)
            return

        await interaction.response.defer()  # Acknowledge button press

        for _ in range(3):
            spinning = " | ".join(random.choices(EMOJIS, k=3))
            await self.message.edit(content=f"🎰 {spinning}")
            await asyncio.sleep(0.4)

        result = [random.choice(EMOJIS) for _ in range(3)]
        result_str = " | ".join(result)

        if result[0] == result[1] == result[2]:
            winnings = int(self.bet * self.multiplier)
            update_balance(self.user.id, winnings)
            log_transaction(self.user.id, f"Won in slots: +${winnings}")
            message = f"🎉 You won! You got **{result_str}**\n💵 You earned **${winnings}** Redmont Dollars!"
            next_multiplier = 1.5
        else:
            update_balance(self.user.id, -self.bet)
            log_transaction(self.user.id, f"Lost in slots: -${self.bet}")
            message = f"😢 You lost. You got **{result_str}**\nBetter luck next time!"
            next_multiplier = 2.0

        await self.message.edit(content=message, view=SlotsView(self.user, self.bet, next_multiplier, self.message))

@bot.tree.command(name="slots", description="Play the slot machine!")
@app_commands.describe(bet="Amount to bet")
async def slots(interaction: discord.Interaction, bet: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return

    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"❌ Invalid bet amount! \n Bet must be between 1 and ${MAX_BET}.", ephemeral=True)
        return

    balance = get_balance(interaction.user.id)
    if balance < bet:
        await interaction.response.send_message("❌ You don't have enough Balance.", ephemeral=True)
        return

    await interaction.response.send_message("🎰 Spinning...", ephemeral=True)
    message = await interaction.original_response()

    for _ in range(3):
        spinning = " | ".join(random.choices(EMOJIS, k=3))
        await message.edit(content=f"🎰 {spinning}")
        await asyncio.sleep(0.4)

    result = [random.choice(EMOJIS) for _ in range(3)]
    result_str = " | ".join(result)

    if result[0] == result[1] == result[2]:
        winnings = bet * 2
        update_balance(interaction.user.id, winnings)
        log_transaction(interaction.user.id, f"Won in slots: +${winnings}")
        msg_text = f"🎉 You won! You got **{result_str}**\n💵 You earned **${winnings}** Redmont Dollars!"
        multiplier = 1.5
    else:
        update_balance(interaction.user.id, -bet)
        log_transaction(interaction.user.id, f"Lost in slots: -${bet}")
        msg_text = f"😢 You lost. You got **{result_str}**\nBetter luck next time!"
        multiplier = 2.0

    await message.edit(content=msg_text, view=SlotsView(interaction.user, bet, multiplier, message))


#Rock Paper Scissors game
class RPSButtons(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet
        self.play_ended = False

    async def play_rps(self, interaction: discord.Interaction, user_choice: str):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return

        choices = ["🪨", "📄", "✂️"]
        bot_choice = random.choice(choices)
        outcome = self.determine_winner(user_choice, bot_choice)
        result_message = f"You chose {user_choice} | Bot chose {bot_choice}\n"

        if outcome == "win":
            winnings = self.bet * 2
            update_balance(self.user_id, winnings)
            log_transaction(self.user_id, f"Won in RPS: +${winnings}")
            result_message += f"🎉 You won {winnings} Redmont Dollars!"
        elif outcome == "lose":
            log_transaction(self.user_id, f"Lost in RPS: -${self.bet}")
            result_message += f"😢 You lost {self.bet} Redmont Dollars!"
        else:
            update_balance(self.user_id, self.bet)
            log_transaction(self.user_id, f"Tie in RPS: ${self.bet}")
            result_message += "🤝 It's a tie! Your bet has been returned."

        self.clear_items()
        self.add_item(PlayAgainButton(self.user_id, self.bet))
        await interaction.response.edit_message(content=result_message, view=self)
        self.play_ended = True

    def determine_winner(self, user, bot):
        wins = {"🪨": "✂️", "📄": "🪨", "✂️": "📄"}
        if user == bot:
            return "tie"
        elif wins[user] == bot:
            return "win"
        else:
            return "lose"

    @discord.ui.button(label="🪨", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "🪨")

    @discord.ui.button(label="📄", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "📄")

    @discord.ui.button(label="✂️", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "✂️")

class PlayAgainButton(discord.ui.Button):
    def __init__(self, user_id, bet):
        super().__init__(label="🔁 Play Again", style=discord.ButtonStyle.success)
        self.user_id = user_id
        self.bet = bet

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can't restart someone else's game!", ephemeral=True)
            return

        balance = get_balance(self.user_id)
        if balance < self.bet:
            await interaction.response.send_message("❌ You don't have enough Balance to play again.", ephemeral=True)
            return

        update_balance(self.user_id, -self.bet)
        view = RPSButtons(user_id=self.user_id, bet=self.bet)
        await interaction.response.edit_message(content="Let's play again!\nChoose your move:", view=view)

@bot.tree.command(name="rps", description="Play Rock Paper Scissors and win Redmont Dollars!")
@app_commands.describe(bet="Amount of Redmont Dollars to bet")
async def rps(interaction: discord.Interaction, bet: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"❌ Invalid bet amount! \n Bet must be between 1 and ${MAX_BET}.", ephemeral=True)
        return

    if balance < bet:
        await interaction.response.send_message("❌ You don't have enough Balance!", ephemeral=True)
        return

    update_balance(user_id, -bet)
    view = RPSButtons(user_id=user_id, bet=bet)

    await interaction.response.send_message(
        content="Let's play Rock Paper Scissors!\nChoose your move:",
        view=view,
        ephemeral=True
    )



#HighLow Game
card_values = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 1
}

# Risk-based multipliers
risk_based_pay_table = {
    2: {"higher": 1.1, "lower": 10.7},
    3: {"higher": 1.1, "lower": 5.3},
    4: {"higher": 1.1, "lower": 3.5},
    5: {"higher": 1.3, "lower": 2.6},
    6: {"higher": 1.5, "lower": 2.1},
    7: {"higher": 1.87, "lower": 1.87},
    8: {"higher": 2.1, "lower": 1.5},
    9: {"higher": 2.6, "lower": 1.3},
    10: {"higher": 3.5, "lower": 1.1},
    11: {"higher": 5.3, "lower": 1.1},
    12: {"higher": 10.7, "lower": 1.1},
}

def draw_card():
    return random.choice(["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q"])

class HighLowButtons(discord.ui.View):
    def __init__(self, user_id, bet, current_card):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet
        self.current_card = current_card

    async def play_highlow(self, interaction, choice):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("🚫 You can't play this game!", ephemeral=True)

        new_card = draw_card()
        old_val = card_values[str(self.current_card)]
        new_val = card_values[str(new_card)]

        if (choice == "higher" and new_val > old_val) or (choice == "lower" and new_val < old_val):
            outcome = "win"
            multiplier = risk_based_pay_table[old_val][choice]
        elif (choice == "higher" and new_val == old_val) or (choice == "lower" and new_val == old_val):
            outcome = "tie"
            multiplier = 1
        else:
            outcome = "lose"
            multiplier = 0
        
        winnings = int(self.bet * multiplier)

        update_balance(self.user_id, winnings)
        log_transaction(self.user_id, f"HighLow game: {outcome} | Bet: ${self.bet} | Winnings: ${winnings}")
        
        if outcome == "win":
            msg = (
        f"🎴 Your card: `{self.current_card}`\n"
        f"🃏 New card: `{new_card}`\n"
        f"🎉 **You won!** \n You guessed correctly and earned **+${winnings}**! 🤑💰\n"
    )
        elif outcome == "lose":
            msg = (
        f"🎴 Your card: `{self.current_card}`\n"
        f"🃏 New card: `{new_card}`\n"
        f"💥 **You lost!** \n Better luck next time. 😞💸\n"
    )
        else:
            msg = (
        f"🎴 Your card: `{self.current_card}`\n"
        f"🃏 New card: `{new_card}`\n"
        f"🤝 **It's a tie!** \n Your bet has been returned. 😐\n"
    )
        view = HighLowPlayAgainView(self.user_id, self.bet)
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary, emoji="🔼")
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_highlow(interaction, "higher")

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary, emoji="🔽")
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_highlow(interaction, "lower")

class HighLowPlayAgainView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success, emoji="🔁")
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("🚫 Only you can restart your game.", ephemeral=True)

        balance = get_balance(self.user_id)
        if self.bet > balance:
            return await interaction.response.send_message("❌ You don't have enough balance to play again.", ephemeral=True)

        update_balance(self.user_id, -self.bet)

        card = draw_card()
        view = HighLowButtons(self.user_id, self.bet, card)
        await interaction.response.send_message(
            content=f"🎴 Your card is `{card}`\nWill the next card be 🔼 higher or 🔽 lower?",
            view=view,
            ephemeral=True
        )

@bot.tree.command(name="highlow", description="Play High-Low card game!")
@app_commands.describe(bet="How much you want to bet")
async def highlow(interaction: discord.Interaction, bet: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return
    user_id = interaction.user.id
    balance = get_balance(user_id)

    if bet <= 0 or bet > MAX_BET:
        return await interaction.response.send_message(f"❌ Invalid bet amount! \n Bet must be between 1 and ${MAX_BET}.", ephemeral=True)

    if bet > balance:
        return await interaction.response.send_message("❌ You don't have enough balance to bet that amount.", ephemeral=True)

    update_balance(user_id, -bet)

    card = draw_card()
    view = HighLowButtons(user_id, bet, card)

    await interaction.response.send_message(
        content=f"🎴 Your card is `{card}`\nWill the next card be 🔼 higher or 🔽 lower?",
        view=view,
        ephemeral=True
    )


# Command to view last 10 transactions
@bot.tree.command(name="transactions", description="View your recent transactions")
async def view_transactions(interaction: discord.Interaction):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You need to `/register` and accept the ToS before using this command.", ephemeral=True)
        return
    user_id = str(interaction.user.id)

    # Load transaction history
    with open("transactions.json", "r") as f:
        transactions = json.load(f)

    user_transactions = transactions.get(user_id, [])

    if not user_transactions:
        await interaction.response.send_message("📭 You don't have any transactions yet.", ephemeral=True)
        return

    # Show the 10 most recent transactions
    recent = user_transactions[-10:][::-1]  # Last 10, newest first
    description = "\n".join(f"- {t}" for t in recent)

    embed = discord.Embed(title="🧾 Recent Transactions", description=description, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Registeration of users
class ToSView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="✅ Accept ToS", style=discord.ButtonStyle.success)
    async def accept_tos(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("⚠️ This isn't your registration session.", ephemeral=True)
            return

        if str(self.user_id) not in registered_users:
            registered_users.append(str(self.user_id))
            save_registered_users(registered_users)

        await interaction.response.edit_message(content="🎉 You are now registered and can use the casino!", view=None)
@bot.tree.command(name="register", description="Register and accept ToS to use the casino")
async def register(interaction: discord.Interaction):
    if is_registered(interaction.user.id):
        await interaction.response.send_message("✅ You are already registered!", ephemeral=True)
        return

    embed = discord.Embed(
        title="📜 Terms of Service",
        description=f"Please read and accept the [Terms of Service]({TOS_LINK}) before using the casino.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, view=ToSView(interaction.user.id), ephemeral=True)


#Lottery - buy ticket
@bot.tree.command(name="buy_ticket", description="Buy tickets for the Lottery! Per ticket costs $100")
@app_commands.describe(quantity="Number of tickets to buy.")
async def buy_ticket(interaction: discord.Interaction, quantity: int):
    if not is_registered(interaction.user.id):
        await interaction.response.send_message("🚫 You must `/register` before buying a lottery ticket.", ephemeral=True)
        return
    
    if quantity <= 0:
        await interaction.response.send_message("Quantity must be at least 1")
        return

    user_id = str(interaction.user.id)
    total_cost = LOTTERY_TICKET_PRICE * quantity
    if get_balance(user_id) < total_cost:
        await interaction.response.send_message("💸 You don't have enough Balance to buy {quantity} ticket!", ephemeral=True)
        return

    update_balance(user_id, -total_cost)
    for _ in range(quantity):
        lottery_entries.append(user_id)
    save_lottery_entries(lottery_entries)

    log_transaction(user_id, f"Bought {quantity} lottery ticket(s) -${total_cost}")
    await interaction.response.send_message(
        f"🎟️ You successfully bought **{quantity}** ticket(s)! Good luck!",
        ephemeral=True
    )

# Draw lottery funtion
async def draw_lottery_winner():
    if not lottery_entries:
        print("No lottery entries this round.")
        return

    winner_id = random.choice(lottery_entries)
    total_pot = len(lottery_entries) * LOTTERY_TICKET_PRICE
    prize = int(total_pot * 0.9)  # 90% to winner

    update_balance(winner_id, prize)
    log_transaction(winner_id, f"🎰 Lottery win: +${prize}")
    save_lottery_entries([])  # Reset entries

    try:
        user = await bot.fetch_user(int(winner_id))
        await user.send(f"🎉 You won this week's Lottery and received **${prize}**!")
        print(f"{user.name} has won ${prize} in the lottery!")
    except Exception as e:
        print("Error sending DM to winner:", e)

    # Announce publicly in a channel
    channel = bot.get_channel(LOTTERY_ANNOUNCE_CHANNEL_ID)
    if channel:
        await channel.send(f"🎉 Congratulations to <@{winner_id}> for winning this week's **Lottery** and taking home **${prize}**!")
    else:
        print("❗ Lottery announcement channel not found.")

# Auto Draw at midnight
last_lottery_draw_date = None
async def lottery_auto_draw():
    await bot.wait_until_ready()
    global last_lottery_draw_date

    while not bot.is_closed():
        now = datetime.now(timezone.utc)

        if (
            now.weekday() == DRAW_DAY and
            now.hour == DRAW_HOUR and
            now.minute == DRAW_MINUTE and
            last_lottery_draw_date != now.date()
        ):
            print("🎯 Running weekly lottery draw...")
            await draw_lottery_winner()
            last_lottery_draw_date = now.date()  # Mark this day as drawn
            await asyncio.sleep(60)  # Prevent rerun during the same minute

        await asyncio.sleep(30)  # Check every 30 seconds


# Lottery Status command
@bot.tree.command(name="lottery_status", description="Check current lottery entries")
@app_commands.default_permissions(administrator=True)
async def lottery_status(interaction: discord.Interaction):
    if not lottery_entries:
        await interaction.response.send_message("📭 No users have entered the lottery yet.", ephemeral=True)
        return

    unique_users = list(set(lottery_entries))
    num_tickets = len(lottery_entries)
    num_users = len(unique_users)

    mentions = []
    for uid in unique_users:
        user = await bot.fetch_user(int(uid))
        mentions.append(user.mention if user else f"`{uid}`")

    description = (
        f"🎟️ **Total Tickets Sold:** {num_tickets}\n"
        f"👥 **Unique Participants:** {num_users}\n"
        f"📋 **Participants:**\n" + ", ".join(mentions)
    )

    embed = discord.Embed(
        title="🎰 Lottery Status",
        description=description,
        color=discord.Color.purple()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(BOT_KEY)

