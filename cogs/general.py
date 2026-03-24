import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="핑", description="봇 응답속도를 확인합니다")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"퐁! 지연시간: {round(self.bot.latency * 1000)}ms")


async def setup(bot: commands.Bot): # 봇이 이 Cog을 로드할 때 실행되는 함수
    await bot.add_cog(General(bot), guilds=[GUILD_ID])
