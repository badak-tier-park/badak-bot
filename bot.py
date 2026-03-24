import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ 봇 온라인: {bot.user} (ID: {bot.user.id})")
    print(f"연결된 서버 수: {len(bot.guilds)}")


@bot.command(name="핑")
async def ping(ctx):
    await ctx.send(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")


bot.run(os.getenv("DISCORD_TOKEN"))
