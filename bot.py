import discord
from discord.ext import commands
from dotenv import load_dotenv
from config import GUILD_ID
from logger import logger
from database import check_db_connection
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    from cogs.admin import NicknameApprovalView, RaceApprovalView, TierApprovalView
    bot.add_view(NicknameApprovalView())
    bot.add_view(RaceApprovalView())
    bot.add_view(TierApprovalView())
    await bot.tree.sync(guild=GUILD_ID)
    logger.info(f"봇 온라인: {bot.user} (ID: {bot.user.id})")
    logger.info(f"연결된 서버 수: {len(bot.guilds)}")
    logger.info("슬래시 커맨드 동기화 완료")
    await check_db_connection()


async def main():
    async with bot:
        await bot.load_extension("cogs.general")
        await bot.load_extension("cogs.user")
        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.schedule")
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
