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


async def sync_user_nickname_immediately(interaction: discord.Interaction, discord_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT nickname, race, tier FROM users WHERE discord_id = :discord_id"),
            {"discord_id": discord_id}
        )
        user = result.fetchone()
        
    if not user:
        return
        
    target_nick = f"{user.nickname} / {user.race} / {user.tier}"
    member = interaction.guild.get_member(discord_id)
    if not member:
        return

    if member.nick != target_nick and member.display_name != target_nick:
        try:
            await member.edit(nick=target_nick)
            logger.info(f"[닉네임동기화성공] {member.display_name} -> {target_nick}")
        except discord.Forbidden:
            logger.warning(f"[닉네임동기화실패] 권한 부족 (서버장 등): {member.display_name}")
            try:
                await member.send(f"⚠️ **닉네임 변경 안내**\n서버의 DB 정보가 업데이트되었으나, 디스코드 권한(서버장 등) 문제로 인해 자동 변경이 실패했습니다.\n원활한 서버 관리를 위해 디스코드 닉네임을 직접 **`{target_nick}`**(으)로 변경해 주시기 바랍니다.")
            except discord.Forbidden:
                pass

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

        await sync_user_nickname_immediately(interaction, req.discord_id)

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
                text("UPDATE users SET race = :race, tier = 'Test', updated_at = NOW() WHERE discord_id = :discord_id"),
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
            await channel.send(f"{member.mention}({nickname})님의 종족 변경 신청이 승인됐습니다. {req.old_value} → **{req.new_value}**\n(종족 변경으로 인해 티어가 **Test** 등급으로 변경되었습니다!)")
            
            # 종족변경 강등 시 테스트 티켓 발급
            try:
                from cogs.waitlist import spawn_test_ticket
                await spawn_test_ticket(interaction.client, req.discord_id, nickname, req.new_value)
            except Exception as e:
                logger.error(f"[테스트 티켓 발급 오류] {e}")
        except Exception:
            pass

        await sync_user_nickname_immediately(interaction, req.discord_id)

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
# View: 티어 변경 승인/거절 (Persistent)
# -----------------------------------------------
class TierApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="approve_tier")
    async def approve(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "tier")

        if not req:
            await interaction.response.edit_message(content="이미 처리된 요청입니다.", embed=None, view=None)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET tier = :tier, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"tier": req.new_value, "discord_id": req.discord_id}
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
            await channel.send(f"{member.mention}({nickname})님의 티어 변경 신청이 승인됐습니다. {req.old_value} → **{req.new_value}**")
            
            # 대기자 현황판 스무스 동기화 (테스트 졸업 시)
            try:
                from cogs.waitlist import sync_waitlist_dashboard
                await sync_waitlist_dashboard(interaction.client)
            except Exception as e:
                logger.error(f"[티어변경 대시보드 갱신오류] {e}")
        except Exception:
            pass

        await sync_user_nickname_immediately(interaction, req.discord_id)

        logger.info(f"[티어변경승인] {interaction.user} → {req.old_value} → {req.new_value}")
        await interaction.response.edit_message(
            content=f"✅ 티어 변경 승인 완료 ({req.old_value} → {req.new_value}) - by {interaction.user.display_name} -",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="reject_tier")
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button):
        req = await fetch_pending_request(interaction.message.id, "tier")

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
            await channel.send(f"{member.mention}({nickname})님의 티어 변경 신청이 거절됐습니다.")
        except Exception:
            pass

        logger.info(f"[티어변경거절] {interaction.user} → {req.old_value} → {req.new_value}")
        await interaction.response.edit_message(
            content=f"❌ 티어 변경 거절 - by {interaction.user.display_name} -",
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
        test_channel = interaction.guild.get_channel(config.TEST_CHANNEL_ID) if config.TEST_CHANNEL_ID else None
        general_channel = interaction.guild.get_channel(config.GENERAL_CHANNEL_ID) if getattr(config, 'GENERAL_CHANNEL_ID', None) else None
        role_text = current_role.mention if current_role else f"알 수 없음 (ID: {config.ADMIN_ROLE_ID})"
        channel_text = current_channel.mention if current_channel else f"알 수 없음 (ID: {config.ADMIN_CHANNEL_ID})"
        test_channel_text = test_channel.mention if test_channel else f"알 수 없음 (ID: {config.TEST_CHANNEL_ID})"
        general_channel_text = general_channel.mention if general_channel else f"알 수 없음"
        sync_time_text = getattr(config, 'SYNC_TIME', '04:00')
        await interaction.response.send_message(
            f"**현재 설정**\n관리자 역할: {role_text}\n관리자 채널: {channel_text}\n테스트 채널: {test_channel_text}\n일반 채널: {general_channel_text}\n동기화 시간: {sync_time_text}",
            ephemeral=True
        )

    @app_commands.command(name="설정", description="관리자 역할, 관리자/테스트/일반 채널, 동기화 시간을 변경합니다")
    @app_commands.rename(role="관리자역할", channel="관리자채널", test_channel="테스트채널", general_channel="일반채널", sync_time="동기화시간")
    @app_commands.describe(role="변경할 관리자 역할", channel="변경할 관리자 채널", test_channel="테스트 인원을 공지할 챼널", general_channel="테스트 인원 호출용 일반 채널", sync_time="매일 동기화 시각 (HH:MM)")
    async def update_config(
        self,
        interaction: discord.Interaction,
        role: discord.Role = None,
        channel: discord.TextChannel = None,
        test_channel: discord.TextChannel = None,
        general_channel: discord.TextChannel = None,
        sync_time: str = None,
    ):
        await interaction.response.defer(ephemeral=True)

        if not role and not channel and not test_channel and not general_channel and not sync_time:
            await interaction.followup.send("변경할 설정(역할, 채널, 동기화시간)을 입력해주세요.", ephemeral=True)
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

        if test_channel:
            set_key(env_path, "TEST_CHANNEL_ID", str(test_channel.id))
            config.TEST_CHANNEL_ID = test_channel.id
            lines.append(f"테스트 채널: {test_channel.mention}")
            logger.info(f"[설정] {interaction.user} → TEST_CHANNEL_ID={test_channel.id}")

        if general_channel:
            set_key(env_path, "GENERAL_CHANNEL_ID", str(general_channel.id))
            config.GENERAL_CHANNEL_ID = general_channel.id
            lines.append(f"일반 호출 채널: {general_channel.mention}")
            logger.info(f"[설정] {interaction.user} → GENERAL_CHANNEL_ID={general_channel.id}")

        if sync_time:
            import re
            if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", sync_time):
                await interaction.response.send_message("❌ 동기화 시간은 `HH:MM` 형식으로 입력해주세요 (예: 04:00).", ephemeral=True)
                return
            set_key(env_path, "SYNC_TIME", sync_time)
            config.SYNC_TIME = sync_time
            lines.append(f"동기화 시간: {sync_time}")
            logger.info(f"[설정] {interaction.user} → SYNC_TIME={sync_time}")
            
            schedule_cog = self.bot.get_cog("Schedule")
            if schedule_cog:
                schedule_cog.restart_loop()

        await interaction.followup.send(
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

    @app_commands.command(name="테스트종료", description="해당 유저의 테스트를 완료하고 확정 티어를 부여합니다")
    @app_commands.rename(target_user="대상유저", final_tier="확정티어")
    @app_commands.choices(final_tier=[
        app_commands.Choice(name="A", value="A"),
        app_commands.Choice(name="B", value="B"),
        app_commands.Choice(name="C", value="C"),
        app_commands.Choice(name="D", value="D"),
        app_commands.Choice(name="E", value="E"),
    ])
    async def complete_test(self, interaction: discord.Interaction, target_user: discord.Member, final_tier: str):
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, race, tier FROM users WHERE discord_id = :discord_id"),
                {"discord_id": target_user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.followup.send("등록된 유저가 아닙니다.", ephemeral=True)
            return

        if user.tier != "Test":
            await interaction.followup.send("해당 유저는 현재 Test 대기자가 아닙니다.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET tier = :tier, updated_at = NOW() WHERE discord_id = :discord_id"),
                {"tier": final_tier, "discord_id": target_user.id}
            )
            await session.commit()

        await sync_user_nickname_immediately(interaction, target_user.id)

        if getattr(config, 'TEST_CHANNEL_ID', None):
            test_channel = interaction.guild.get_channel(config.TEST_CHANNEL_ID)
            if test_channel:
                try:
                    async for message in test_channel.history(limit=100):
                        if not message.embeds:
                            continue
                        embed = message.embeds[0]
                        if embed.description and f"<@{target_user.id}>" in embed.description and "[테스트 대기]" in embed.title:
                            embed.title = "✅ [테스트 완료]"
                            embed.color = 0x808080 
                            embed.description += f"\n\n**[결과]** 확정 티어: **{final_tier}**"
                            await message.edit(embed=embed, view=None)
                            break
                except Exception as e:
                    logger.error(f"[테스트 메시지 수정 실패] {e}")

        logger.info(f"[테스트종료] {interaction.user} 가 {target_user.display_name}의 테스트를 종료함. ({final_tier}으로 배정)")
        await interaction.followup.send(f"✅ {target_user.mention}({user.nickname})님의 테스트가 종료되어 **{final_tier}** 티어로 배정되었습니다.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot), guilds=[GUILD_ID])
