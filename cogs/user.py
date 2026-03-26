import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID, ADMIN_CHANNEL_ID
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

            # 길드 소유자는 자동으로 관리자 권한 부여
            is_owner = interaction.user.id == interaction.guild.owner_id
            await session.execute(
                text("INSERT INTO users (discord_id, nickname, race, tier, is_admin) VALUES (:discord_id, :nickname, :race, :tier, :is_admin)"),
                {"discord_id": interaction.user.id, "nickname": self.nickname, "race": self.race, "tier": self.tier, "is_admin": is_owner}
            )
            await session.commit()

        if is_owner:
            import config
            role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            if role:
                await interaction.user.add_roles(role)

        logger.info(f"[유저등록] {interaction.user} (ID: {interaction.user.id}) | 닉네임: {self.nickname} | 종족: {self.race} | 티어: {self.tier} | 관리자: {is_owner}")
        await interaction.response.edit_message(content="✅ 등록이 완료됐습니다.", view=None)
        await interaction.channel.send(f"🎉 **{self.nickname}** 님이 등록됐습니다! (종족: {self.race} / 티어: {self.tier})")


# -----------------------------------------------
# Cog: 유저 관리 명령어
# -----------------------------------------------
class User(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="유저등록", description="유저 정보를 등록합니다")
    async def register(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            if result.fetchone():
                await interaction.response.send_message("이미 등록된 유저입니다.", ephemeral=True)
                return

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

    @app_commands.command(name="닉네임변경신청", description="닉네임 변경을 신청합니다 (관리자 승인 필요)")
    @app_commands.describe(nickname="변경할 닉네임")
    async def request_nickname(self, interaction: discord.Interaction, nickname: str):
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.followup.send("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.")
            return

        try:
            admin_channel = await self.bot.fetch_channel(ADMIN_CHANNEL_ID)
            embed = discord.Embed(title="📝 닉네임 변경 신청", color=0xffa500)
            embed.add_field(name="신청자", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="현재 닉네임", value=user.nickname, inline=False)
            embed.add_field(name="변경 닉네임", value=nickname, inline=False)

            from cogs.admin import NicknameApprovalView
            await admin_channel.send(
                embed=embed,
                view=NicknameApprovalView(interaction.user.id, nickname)
            )

            logger.info(f"[닉네임변경신청] {interaction.user} | {user.nickname} → {nickname}")
            await interaction.followup.send("✅ 닉네임 변경 신청이 완료됐습니다. 관리자 승인을 기다려주세요.")
        except Exception as e:
            logger.error(f"[닉네임변경신청 오류] {e}")
            await interaction.followup.send("오류가 발생했습니다. 관리자에게 문의해주세요.")

    @app_commands.command(name="종족변경신청", description="종족 변경을 신청합니다 (관리자 승인 필요)")
    @app_commands.choices(race=[
        app_commands.Choice(name="테란", value="T"),
        app_commands.Choice(name="저그", value="Z"),
        app_commands.Choice(name="프로토스", value="P"),
    ])
    async def request_race(self, interaction: discord.Interaction, race: str):
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, race FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.followup.send("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.")
            return

        admin_channel = await self.bot.fetch_channel(ADMIN_CHANNEL_ID)
        embed = discord.Embed(title="📝 종족 변경 신청", color=0xffa500)
        embed.add_field(name="신청자", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="닉네임", value=user.nickname, inline=False)
        embed.add_field(name="현재 종족", value=user.race, inline=False)
        embed.add_field(name="변경 종족", value=race, inline=False)

        from cogs.admin import RaceApprovalView
        await admin_channel.send(
            embed=embed,
            view=RaceApprovalView(interaction.user.id, user.nickname, race)
        )

        logger.info(f"[종족변경신청] {interaction.user} | {user.race} → {race}")
        await interaction.followup.send("✅ 종족 변경 신청이 완료됐습니다. 관리자 승인을 기다려주세요.")


async def setup(bot: commands.Bot):
    await bot.add_cog(User(bot), guilds=[GUILD_ID])
