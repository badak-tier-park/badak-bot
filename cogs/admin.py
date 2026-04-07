import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID
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
        await interaction.response.defer()
        
        if not self.selected_user:
            await interaction.followup.send("유저를 선택해주세요.", ephemeral=True)
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
            await interaction.edit_original_response(content="등록되지 않은 유저입니다.", view=None)
            return

        if user.is_admin:
            await interaction.edit_original_response(content="이미 관리자입니다.", view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET is_admin = TRUE WHERE discord_id = :discord_id"),
                {"discord_id": self.selected_user.id}
            )
            await session.commit()

        guild = interaction.guild
        role = guild.get_role(config.ADMIN_ROLE_ID)
        try:
            member = await guild.fetch_member(self.selected_user.id)
            if role and member:
                await member.add_roles(role)
        except discord.Forbidden:
            logger.warning(f"[관리자등록] 권한 부족 (봇 역할 계층순위 또는 권한 확인 필요): 유저={self.selected_user.id}")
        except Exception as e:
            logger.warning(f"[관리자등록] 역할 지급 중 오류: {e}")

        logger.info(f"[관리자등록] {interaction.user} (ID: {interaction.user.id}) → {user.nickname} (ID: {self.selected_user.id})")
        await interaction.edit_original_response(content="✅ 완료됐습니다.", view=None)
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
        await interaction.response.defer()
        
        if not self.selected_user:
            await interaction.followup.send("유저를 선택해주세요.", ephemeral=True)
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
            await interaction.edit_original_response(content="등록되지 않은 유저입니다.", view=None)
            return

        if not user.is_admin:
            await interaction.edit_original_response(content="관리자가 아닙니다.", view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET is_admin = FALSE WHERE discord_id = :discord_id"),
                {"discord_id": self.selected_user.id}
            )
            await session.commit()

        guild = interaction.guild
        role = guild.get_role(config.ADMIN_ROLE_ID)
        try:
            member = await guild.fetch_member(self.selected_user.id)
            if role and member:
                await member.remove_roles(role)
        except discord.Forbidden:
            logger.warning(f"[관리자해제] 권한 부족 (봇 역할 계층순위 또는 권한 확인 필요): 유저={self.selected_user.id}")
        except Exception as e:
            logger.warning(f"[관리자해제] 역할 회수 중 오류: {e}")

        logger.info(f"[관리자해제] {interaction.user} (ID: {interaction.user.id}) → {user.nickname} (ID: {self.selected_user.id})")
        await interaction.edit_original_response(content="✅ 완료됐습니다.", view=None)
        await interaction.channel.send(f"🔓 **{user.nickname}** 의 관리자가 해제됐습니다. - by {interaction.user.display_name}({executor_nickname}) -")


# -----------------------------------------------
# Helpers
# -----------------------------------------------
async def fetch_pending_request(message_id: int, req_type: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM change_requests WHERE message_id = :message_id AND type = :type AND status = 'pending'"),
            {"message_id": message_id, "type": req_type}
        )
        return result.fetchone()


async def get_user_nickname(discord_id: int) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT nickname FROM users WHERE discord_id = :discord_id"),
            {"discord_id": discord_id}
        )
        row = result.fetchone()
        return row[0] if row else str(discord_id)


# -----------------------------------------------
# View: 닉네임 변경 승인/거절 (Persistent)
# -----------------------------------------------
class NicknameApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="approve_nickname")
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "nickname")

        if not req:
            await interaction.response.edit_message(content="이미 처리된 요청입니다.", embed=None, view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET nickname = :nickname, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"nickname": req.new_value, "discord_id": req.discord_id}
            )
            await session.execute(
                text("UPDATE change_requests SET status = 'approved' WHERE id = :id"),
                {"id": req.id}
            )
            await session.commit()

        try:
            channel = interaction.guild.get_channel(req.channel_id)
            member = await interaction.guild.fetch_member(req.discord_id)
            await channel.send(f"{member.mention}({req.new_value})님의 닉네임 변경 신청이 승인됐습니다. {req.old_value} → **{req.new_value}**")
        except Exception:
            pass

        logger.info(f"[닉네임변경승인] {interaction.user} → {req.old_value} → {req.new_value}")
        await interaction.response.edit_message(
            content=f"✅ 닉네임 변경 승인 완료 ({req.old_value} → {req.new_value}) - by {interaction.user.display_name} -",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="reject_nickname")
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "nickname")

        if not req:
            await interaction.response.edit_message(content="이미 처리된 요청입니다.", embed=None, view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE change_requests SET status = 'rejected' WHERE id = :id"),
                {"id": req.id}
            )
            await session.commit()

        try:
            channel = interaction.guild.get_channel(req.channel_id)
            member = await interaction.guild.fetch_member(req.discord_id)
            await channel.send(f"{member.mention}({req.old_value})님의 닉네임 변경 신청이 거절됐습니다.")
        except Exception:
            pass

        logger.info(f"[닉네임변경거절] {interaction.user} → {req.old_value} → {req.new_value}")
        await interaction.response.edit_message(
            content=f"❌ 닉네임 변경 거절 - by {interaction.user.display_name} -",
            embed=None,
            view=None
        )


# -----------------------------------------------
# View: 종족 변경 승인/거절 (Persistent)
# -----------------------------------------------
class RaceApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="approve_race")
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "race")

        if not req:
            await interaction.response.edit_message(content="이미 처리된 요청입니다.", embed=None, view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET race = :race, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"race": req.new_value, "discord_id": req.discord_id}
            )
            await session.execute(
                text("UPDATE change_requests SET status = 'approved' WHERE id = :id"),
                {"id": req.id}
            )
            await session.commit()

        try:
            nickname = await get_user_nickname(req.discord_id)
            channel = interaction.guild.get_channel(req.channel_id)
            member = await interaction.guild.fetch_member(req.discord_id)
            await channel.send(f"{member.mention}({nickname})님의 종족 변경 신청이 승인됐습니다. {req.old_value} → **{req.new_value}**")
        except Exception:
            pass

        logger.info(f"[종족변경승인] {interaction.user} → {req.old_value} → {req.new_value}")
        await interaction.response.edit_message(
            content=f"✅ 종족 변경 승인 완료 ({req.old_value} → {req.new_value}) - by {interaction.user.display_name} -",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="reject_race")
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "race")

        if not req:
            await interaction.response.edit_message(content="이미 처리된 요청입니다.", embed=None, view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE change_requests SET status = 'rejected' WHERE id = :id"),
                {"id": req.id}
            )
            await session.commit()

        try:
            nickname = await get_user_nickname(req.discord_id)
            channel = interaction.guild.get_channel(req.channel_id)
            member = await interaction.guild.fetch_member(req.discord_id)
            await channel.send(f"{member.mention}({nickname})님의 종족 변경 신청이 거절됐습니다.")
        except Exception:
            pass

        logger.info(f"[종족변경거절] {interaction.user} → {req.old_value} → {req.new_value}")
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

        role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
        if not role:
            await interaction.response.send_message(
                "⚠️ 관리자 역할이 설정되어 있지 않습니다.\n"
                "Discord에서 관리자 역할을 먼저 생성해주세요.\n"
                "역할이 생성되어 있다면 `/설정` 명령어로 관리자 역할을 지정해주세요.",
                ephemeral=True
            )
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
