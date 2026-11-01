import os
import json
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")  # set this as an environment variable
DATA_FILE = "graveyard.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- storage ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def record(guild_id, user, died: bool):
    data = load_data()
    g = data.setdefault(str(guild_id), {})
    u = g.setdefault(str(user.id), {"name": user.name, "deaths": 0, "survivals": 0})
    u["name"] = user.name
    u["deaths" if died else "survivals"] += 1
    save_data(data)
    return u

# ---------- flavor text ----------
DRAMA = [
    "🥁 *drumroll intensifies*",
    "🪙 The coin is flipped high into the air...",
    "😰 The crowd holds its breath...",
    "🌀 It spins... and spins...",
]

DOOM = [
    "🪓 **OFF WITH THEIR HEAD!** {name} has been executed. Their snacks will be redistributed.",
    "⚰️ {name} has been yeeted into the shadow realm. Press F.",
    "💀 The coin has spoken. {name} is no more. Someone tell their mom.",
    "🔥 {name} was found guilty of vibing incorrectly. Sentence: immediate exile.",
    "🦆 A goose has dragged {name} away. There is nothing we can do.",
]

SPARE = [
    "😇 **SPARED!** {name} lives to cause chaos another day.",
    "🍀 The coin shows mercy. {name} walks free... for now.",
    "🛡️ {name} dodged the guillotine like it was a dodgeball. Respect.",
    "🎉 {name} survives! The executioner goes home disappointed.",
    "🐸 A frog jumped on the lever. {name} is saved by pure frog energy.",
]

# ---------- the trial ----------
async def run_trial(interaction: discord.Interaction, target: discord.Member):
    guild = interaction.guild

    if target.bot:
        return await interaction.response.send_message("🤖 Bots have diplomatic immunity.", ephemeral=True)
    if target.id == guild.owner_id:
        return await interaction.response.send_message("👑 The server owner cannot be executed. They own the guillotine.", ephemeral=True)
    if target.top_role >= guild.me.top_role:
        return await interaction.response.send_message(
            f"🛡️ {target.display_name}'s role is too powerful for my axe. (Move my role higher.)", ephemeral=True)

    await interaction.response.send_message(
        f"⚖️ **THE COURT IS NOW IN SESSION**\n{target.mention} stands before the guillotine...")

    text = f"⚖️ **THE COURT IS NOW IN SESSION**\n{target.mention} stands before the guillotine..."
    for line in DRAMA:
        await asyncio.sleep(1.5)
        text += f"\n{line}"
        await interaction.edit_original_response(content=text)

    await asyncio.sleep(2)
    doomed = random.random() < 0.5

    if doomed:
        # make a one-use invite so they can come back after a pardon
        invite_url = None
        try:
            invite = await interaction.channel.create_invite(
                max_uses=1, max_age=0, unique=True, reason="Return ticket from the afterlife")
            invite_url = invite.url
        except discord.HTTPException:
            pass

        try:
            await target.send(
                f"💀 You were executed in **{guild.name}** by the 50/50 guillotine.\n"
                f"Beg a mod for a `/pardon`, then use this to come back: {invite_url or '(ask a mod for an invite)'}")
        except discord.HTTPException:
            pass  # DMs closed

        try:
            await guild.ban(target, reason="Lost the 50/50 guillotine", delete_message_seconds=0)
        except discord.HTTPException:
            return await interaction.edit_original_response(
                content=text + "\n\n😬 The blade got stuck. (I'm missing Ban Members permission.)")

        stats = record(guild.id, target, died=True)
        verdict = random.choice(DOOM).format(name=f"**{target.display_name}**")
        verdict += f"\n☠️ Death count: **{stats['deaths']}**"
    else:
        stats = record(guild.id, target, died=False)
        verdict = random.choice(SPARE).format(name=target.mention)
        verdict += f"\n🍀 Survivals: **{stats['survivals']}**"

    await interaction.edit_original_response(content=text + "\n\n" + verdict)

# ---------- commands ----------
@bot.tree.command(name="roulette", description="Put yourself on trial. 50/50. Good luck.")
async def roulette(interaction: discord.Interaction):
    await run_trial(interaction, interaction.user)

@bot.tree.command(name="execute", description="Drag someone to the guillotine (50/50 ban).")
@app_commands.describe(target="The accused")
@app_commands.checks.has_permissions(ban_members=True)
async def execute(interaction: discord.Interaction, target: discord.Member):
    await run_trial(interaction, target)

@bot.tree.command(name="pardon", description="Bring someone back from the dead (unban).")
@app_commands.describe(user="The fallen (paste their user ID if needed)")
@app_commands.checks.has_permissions(ban_members=True)
async def pardon(interaction: discord.Interaction, user: discord.User):
    try:
        await interaction.guild.unban(user, reason=f"Pardoned by {interaction.user}")
        await interaction.response.send_message(
            f"✨ **RESURRECTION!** {user.name} has been pardoned by the crown. They may return to the land of the living.")
    except discord.NotFound:
        await interaction.response.send_message(f"🤔 {user.name} isn't dead. Yet.", ephemeral=True)

@bot.tree.command(name="graveyard", description="See who has died the most.")
async def graveyard(interaction: discord.Interaction):
    data = load_data().get(str(interaction.guild.id), {})
    if not data:
        return await interaction.response.send_message("🌱 The graveyard is empty. Suspiciously peaceful.")

    ranked = sorted(data.values(), key=lambda u: (u["deaths"], -u["survivals"]), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, u in enumerate(ranked):
        icon = medals[i] if i < 3 else "🪦"
        lines.append(f"{icon} **{u['name']}** — ☠️ {u['deaths']} deaths | 🍀 {u['survivals']} survived")

    embed = discord.Embed(title="⚰️ THE GRAVEYARD ⚰️", description="\n".join(lines), color=0x2b2d31)
    embed.set_footer(text="Rest in pieces.")
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "🚫 Only the royal executioners (mods) can do that."
    else:
        msg = f"⚠️ Something broke: `{error}`"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🪓 Guillotine ready as {bot.user}")

bot.run(TOKEN)
