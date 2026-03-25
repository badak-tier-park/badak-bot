import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID, ADMIN_ROLE_ID
from database import AsyncSessionLocal
from sqlalchemy import text
from logger import logger


# -----------------------------------------------
# View: Discord UserSelect
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
# Cog: 관리자 관리 명령어
# -----------------------------------------------
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="관리자등록", description="유저를 관리자로 등록합니다")
    @app_commands.default_permissions(manage_roles=True) # 운영진 역할과 역할 관리 권한이 있어야 사용 가능
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
