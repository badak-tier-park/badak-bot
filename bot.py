import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


GUILD_ID = discord.Object(id=1485512072748859515)


@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD_ID)
    print(f"✅ 봇 온라인: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}")
    print("슬래시 커맨드 동기화 완료")


@bot.tree.command(name="핑", description="봇 응답속도를 확인합니다", guild=GUILD_ID)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")


bot.run(os.getenv("DISCORD_TOKEN"))
