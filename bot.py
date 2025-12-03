import os
import json
import asyncio
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

DATA_FILE = "deadlines.json"
message_cache = {}  # Stores message objects while bot is running


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            f.write("{}")
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


deadlines = load_data()


def build_progress(current, total, size=20, style="clean"):
    percent = max(0, min(current / total, 1))
    filled = int(percent * size)

    styles = {
        "clean": ("█", "░"),
        "bracket": ("■", "□"),
        "emoji": ("🟩", "⬜"),
        "smooth": ("▓", "░"),
        "minimal": ("▰", "▱"),
    }

    if style not in styles:
        style = "clean"

    full, empty = styles[style]
    bar = full * filled + empty * (size - filled)

    return bar, percent * 100


async def update_progress(channel_id, channel):
    """Update progress bar for a specific channel"""

    if str(channel_id) not in deadlines:
        return

    data = deadlines[str(channel_id)]
    end_date = datetime.fromisoformat(data["deadline"])
    creation_date = datetime.fromisoformat(data["created"])
    message_id = int(data["message"])

    try:
        msg = await channel.fetch_message(message_id)
    except:
        return  # message was deleted
    
    while True:
        now = datetime.now()
        total_seconds = (end_date - creation_date).total_seconds()
        progress_seconds = (now - creation_date).total_seconds()

        if progress_seconds >= total_seconds:
            finished = discord.Embed(
                title="🎉 Deadline Reached!",
                description=f"**{end_date.date()}** has arrived!",
                color=discord.Color.green()
            )
            await msg.edit(embed=finished)
            del deadlines[str(channel_id)]
            save_data(deadlines)
            break

        bar, percent = build_progress(progress_seconds, total_seconds, style="smooth")

        embed = discord.Embed(
            title="⏳ Deadline Progress",
            color=discord.Color.blurple()
        )

        embed.add_field(name="📅 Deadline", value=f"`{end_date.date()}`", inline=False)
        embed.add_field(name="📊 Progress", value=f"```{bar}  {percent:.2f}%```", inline=False)
        days_left = int((end_date - now).days)
        embed.add_field(name="⏳ Time Left", value=f"`{days_left} days`", inline=True)
        await msg.edit(embed=embed)

    await asyncio.sleep(3600)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 Logged in as {bot.user}")

    # Resume unfinished deadlines
    for channel_id, data in deadlines.items():
        channel = bot.get_channel(int(channel_id))
        if channel:
            print(f"Resuming deadline in channel {channel_id}")
            asyncio.create_task(update_progress(int(channel_id), channel))


@bot.tree.command(name="deadline", description="Set a deadline (DD-MM-YYYY)")
async def deadline(interaction: discord.Interaction, date: str):
    try:
        end_date = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        await interaction.response.send_message("❌ Use format: YYYY-MM-DD")
        return

    if end_date <= datetime.now():
        await interaction.response.send_message("❌ Deadline must be in the future.")
        return

    await interaction.response.send_message(f"⏳ Creating deadline for {date}...")
    msg = await interaction.original_response()

    deadlines[str(interaction.channel_id)] = {
        "deadline": end_date.isoformat(),
        "created": datetime.now().isoformat(),
        "message": msg.id,
    }
    save_data(deadlines)

    asyncio.create_task(update_progress(interaction.channel_id, interaction.channel))


@bot.tree.command(name="clear_deadline", description="Remove saved deadline")
async def clear_deadline(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)

    if channel_id in deadlines:
        del deadlines[channel_id]
        save_data(deadlines)
        await interaction.response.send_message("🧹 Deadline cleared!")
    else:
        await interaction.response.send_message("⚠️ No deadline set.")


bot.run(TOKEN)