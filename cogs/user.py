import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID
from database import AsyncSessionLocal
from sqlalchemy import text
from logger import logger

# -----------------------------------------------
# Modal: 닉네임 입력
# -----------------------------------------------
class RegisterModal(discord.ui.Modal, title="유저 등록"):
    nickname = discord.ui.TextInput(
        label="닉네임",
        placeholder="사용할 닉네임을 입력하세요",
        min_length=1,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        view = RegisterSelectView(self.nickname.value)
        await interaction.response.send_message(
            "종족과 티어를 선택해주세요.",
            view=view,
            ephemeral=True
        )

# -----------------------------------------------
# View: 종족 / 티어 선택
# -----------------------------------------------
class RegisterSelectView(discord.ui.View):
    def __init__(self, nickname: str):
        super().__init__(timeout=60)
        self.nickname = nickname
        self.race = None
        self.tier = None

    @discord.ui.select(
        placeholder="종족을 선택하세요",
        options=[
            discord.SelectOption(label="테란", value="T"),
            discord.SelectOption(label="저그", value="Z"),
            discord.SelectOption(label="프로토스", value="P"),
        ]
    )
    async def race_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.race = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        placeholder="티어를 선택하세요",
        options=[
            discord.SelectOption(label="A", value="A"),
            discord.SelectOption(label="B", value="B"),
            discord.SelectOption(label="C", value="C"),
            discord.SelectOption(label="D", value="D"),
            discord.SelectOption(label="E", value="E"),
        ]
    )
    async def tier_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.tier = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="등록", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.race or not self.tier:
            await interaction.response.send_message("종족과 티어를 모두 선택해주세요.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            if result.fetchone():
                await interaction.response.edit_message(content="이미 등록된 유저입니다.", view=None)
                return

            await session.execute(
                text("INSERT INTO users (discord_id, nickname, race, tier) VALUES (:discord_id, :nickname, :race, :tier)"),
                {"discord_id": interaction.user.id, "nickname": self.nickname, "race": self.race, "tier": self.tier}
            )
            await session.commit()

        logger.info(f"[유저등록] {interaction.user} (ID: {interaction.user.id}) | 닉네임: {self.nickname} | 종족: {self.race} | 티어: {self.tier}")
        await interaction.response.edit_message(
            content=f"✅ 등록 완료!\n닉네임: {self.nickname} / 종족: {self.race} / 티어: {self.tier}",
            view=None
        )

# -----------------------------------------------
# Cog: 유저 관리 명령어
# -----------------------------------------------
class User(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="유저등록", description="유저 정보를 등록합니다")
    async def register(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterModal())

    @app_commands.command(name="유저목록", description="등록된 유저 목록을 확인합니다")
    async def user_list(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, race, tier FROM users ORDER BY created_at DESC")
            )
            users = result.fetchall()

        if not users:
            await interaction.response.send_message("등록된 유저가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 유저 목록", color=0x00aaff)
        for user in users:
            embed.add_field(
                name="\u200b",
                value=f"{user.nickname} / {user.race} / {user.tier}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="종족변경", description="종족을 변경합니다")
    @app_commands.choices(race=[
        app_commands.Choice(name="테란", value="T"),
        app_commands.Choice(name="저그", value="Z"),
        app_commands.Choice(name="프로토스", value="P"),
    ])
    async def change_race(self, interaction: discord.Interaction, race: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("UPDATE users SET race = :race, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"race": race, "discord_id": interaction.user.id}
            )
            await session.commit()

        if result.rowcount == 0:
            await interaction.response.send_message("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ 종족이 **{race}** 으로 변경되었습니다.")

    @app_commands.command(name="닉네임변경", description="닉네임을 변경합니다")
    @app_commands.describe(nickname="변경할 닉네임")
    async def change_nickname(self, interaction: discord.Interaction, nickname: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("UPDATE users SET nickname = :nickname, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"nickname": nickname, "discord_id": interaction.user.id}
            )
            await session.commit()

        if result.rowcount == 0:
            await interaction.response.send_message("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ 닉네임이 **{nickname}** 으로 변경되었습니다.")


async def setup(bot: commands.Bot):
    await bot.add_cog(User(bot), guilds=[GUILD_ID])
