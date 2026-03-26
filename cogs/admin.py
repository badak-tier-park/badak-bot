import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID, ADMIN_ROLE_ID
from database import AsyncSessionLocal
from sqlalchemy import text
from logger import logger
from dotenv import set_key, find_dotenv
import config


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
            executor = await session.execute(
                text("SELECT nickname FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            executor_nickname = (executor.fetchone() or [interaction.user.display_name])[0]

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
        await interaction.response.edit_message(content="✅ 완료됐습니다.", view=None)
        await interaction.channel.send(f"🛡️ **{user.nickname}** 이(가) 관리자로 등록됐습니다. - by {interaction.user.display_name}({executor_nickname}) -")


# -----------------------------------------------
# View: 관리자 해제 - Discord UserSelect
# -----------------------------------------------
class AdminRemoveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_user = None

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="유저를 검색하세요")
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.selected_user = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="해제", style=discord.ButtonStyle.danger)
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
            executor = await session.execute(
                text("SELECT nickname FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            executor_nickname = (executor.fetchone() or [interaction.user.display_name])[0]

        if not user:
            await interaction.response.edit_message(content="등록되지 않은 유저입니다.", view=None)
            return

        if not user.is_admin:
            await interaction.response.edit_message(content="관리자가 아닙니다.", view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET is_admin = FALSE WHERE discord_id = :discord_id"),
                {"discord_id": self.selected_user.id}
            )
            await session.commit()

        guild = interaction.guild
        role = guild.get_role(config.ADMIN_ROLE_ID)
        member = await guild.fetch_member(self.selected_user.id)
        if role and member:
            await member.remove_roles(role)

        logger.info(f"[관리자해제] {interaction.user} (ID: {interaction.user.id}) → {user.nickname} (ID: {self.selected_user.id})")
        await interaction.response.edit_message(content="✅ 완료됐습니다.", view=None)
        await interaction.channel.send(f"🔓 **{user.nickname}** 의 관리자가 해제됐습니다. - by {interaction.user.display_name}({executor_nickname}) -")


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
            content=f"✅ 닉네임 변경 승인 완료 - by {interaction.user.display_name} -",
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
            content=f"❌ 닉네임 변경 거절 - by {interaction.user.display_name} -",
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
            content=f"✅ 종족 변경 승인 완료 - by {interaction.user.display_name} -",
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
            content=f"❌ 종족 변경 거절 - by {interaction.user.display_name} -",
            embed=None,
            view=None
        )


# -----------------------------------------------
# Cog: 관리자 관리 명령어
# -----------------------------------------------
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="설정보기", description="현재 설정을 확인합니다")
    async def view_config(self, interaction: discord.Interaction):
        current_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
        current_channel = interaction.guild.get_channel(config.ADMIN_CHANNEL_ID)
        role_text = current_role.mention if current_role else f"알 수 없음 (ID: {config.ADMIN_ROLE_ID})"
        channel_text = current_channel.mention if current_channel else f"알 수 없음 (ID: {config.ADMIN_CHANNEL_ID})"
        await interaction.response.send_message(
            f"**현재 설정**\n관리자 역할: {role_text}\n관리자 채널: {channel_text}",
            ephemeral=True
        )

    @app_commands.command(name="설정", description="관리자 역할 또는 관리자 채널을 변경합니다")
    @app_commands.rename(role="관리자역할", channel="관리자채널")
    @app_commands.describe(role="변경할 관리자 역할", channel="변경할 관리자 채널")
    async def update_config(
        self,
        interaction: discord.Interaction,
        role: discord.Role = None,
        channel: discord.TextChannel = None,
    ):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("서버 장만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return

        if not role and not channel:
            await interaction.response.send_message("변경할 관리자역할 또는 관리자채널을 입력해주세요.", ephemeral=True)
            return

        env_path = find_dotenv()
        lines = []

        if role:
            set_key(env_path, "ADMIN_ROLE_ID", str(role.id))
            config.ADMIN_ROLE_ID = role.id
            lines.append(f"관리자 역할: {role.mention}")
            logger.info(f"[설정] {interaction.user} → ADMIN_ROLE_ID={role.id}")

        if channel:
            set_key(env_path, "ADMIN_CHANNEL_ID", str(channel.id))
            config.ADMIN_CHANNEL_ID = channel.id
            lines.append(f"관리자 채널: {channel.mention}")
            logger.info(f"[설정] {interaction.user} → ADMIN_CHANNEL_ID={channel.id}")

        await interaction.response.send_message(
            "✅ 설정이 변경됐습니다.\n" + "\n".join(lines),
            ephemeral=True
        )

    @app_commands.command(name="관리자등록", description="유저를 관리자로 등록합니다")
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

    @app_commands.command(name="관리자해제", description="관리자를 해제합니다")
    async def remove_admin(self, interaction: discord.Interaction):
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
            "관리자를 해제할 유저를 선택하세요.",
            view=AdminRemoveView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot), guilds=[GUILD_ID])
