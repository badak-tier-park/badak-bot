import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID, ADMIN_ROLE_ID
from database import AsyncSessionLocal
from sqlalchemy import text
from logger import logger


# -----------------------------------------------
# View: 관리자 등록 - Discord UserSelect
# -----------------------------------------------
class AdminUserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_user = None

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="유저를 검색하세요")
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.selected_user = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="등록", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.selected_user:
            await interaction.response.send_message("유저를 선택해주세요.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, is_admin FROM users WHERE discord_id = :discord_id"),
                {"discord_id": self.selected_user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.response.edit_message(content="등록되지 않은 유저입니다.", view=None)
            return

        if user.is_admin:
            await interaction.response.edit_message(content="이미 관리자입니다.", view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET is_admin = TRUE WHERE discord_id = :discord_id"),
                {"discord_id": self.selected_user.id}
            )
            await session.commit()

        guild = interaction.guild
        role = guild.get_role(ADMIN_ROLE_ID)
        member = await guild.fetch_member(self.selected_user.id)
        if role and member:
            await member.add_roles(role)

        logger.info(f"[관리자등록] {interaction.user} (ID: {interaction.user.id}) → {user.nickname} (ID: {self.selected_user.id})")
        await interaction.response.edit_message(
            content=f"✅ **{user.nickname}** 을(를) 관리자로 등록했습니다.",
            view=None
        )


# -----------------------------------------------
# View: 닉네임 변경 승인/거절
# -----------------------------------------------
class NicknameApprovalView(discord.ui.View):
    def __init__(self, discord_id: int, new_nickname: str):
        super().__init__(timeout=None)
        self.discord_id = discord_id
        self.new_nickname = new_nickname

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET nickname = :nickname, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"nickname": self.new_nickname, "discord_id": self.discord_id}
            )
            await session.commit()

        try:
            member = await interaction.guild.fetch_member(self.discord_id)
            await member.send(f"✅ 닉네임 변경 신청이 승인됐습니다.\n변경된 닉네임: **{self.new_nickname}**")
        except Exception:
            pass

        logger.info(f"[닉네임변경승인] {interaction.user} → discord_id: {self.discord_id} | 닉네임: {self.new_nickname}")
        await interaction.response.edit_message(
            content=f"✅ 닉네임 변경 승인 완료 (by {interaction.user.display_name})",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            member = await interaction.guild.fetch_member(self.discord_id)
            await member.send("❌ 닉네임 변경 신청이 거절됐습니다.")
        except Exception:
            pass

        logger.info(f"[닉네임변경거절] {interaction.user} → discord_id: {self.discord_id}")
        await interaction.response.edit_message(
            content=f"❌ 닉네임 변경 거절 (by {interaction.user.display_name})",
            embed=None,
            view=None
        )


# -----------------------------------------------
# View: 종족 변경 승인/거절
# -----------------------------------------------
class RaceApprovalView(discord.ui.View):
    def __init__(self, discord_id: int, nickname: str, new_race: str):
        super().__init__(timeout=None)
        self.discord_id = discord_id
        self.nickname = nickname
        self.new_race = new_race

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET race = :race, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"race": self.new_race, "discord_id": self.discord_id}
            )
            await session.commit()

        try:
            member = await interaction.guild.fetch_member(self.discord_id)
            await member.send(f"✅ 종족 변경 신청이 승인됐습니다.\n변경된 종족: **{self.new_race}**")
        except Exception:
            pass

        logger.info(f"[종족변경승인] {interaction.user} → {self.nickname} | 종족: {self.new_race}")
        await interaction.response.edit_message(
            content=f"✅ 종족 변경 승인 완료 (by {interaction.user.display_name})",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            member = await interaction.guild.fetch_member(self.discord_id)
            await member.send("❌ 종족 변경 신청이 거절됐습니다.")
        except Exception:
            pass

        logger.info(f"[종족변경거절] {interaction.user} → {self.nickname}")
        await interaction.response.edit_message(
            content=f"❌ 종족 변경 거절 (by {interaction.user.display_name})",
            embed=None,
            view=None
        )


# -----------------------------------------------
# Cog: 관리자 관리 명령어
# -----------------------------------------------
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="관리자등록", description="유저를 관리자로 등록합니다")
    @app_commands.default_permissions(manage_roles=True)
    async def register_admin(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT is_admin FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            user = result.fetchone()

        if not user or not user.is_admin:
            await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return

        await interaction.response.send_message(
            "관리자로 등록할 유저를 선택하세요.",
            view=AdminUserSelectView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot), guilds=[GUILD_ID])
