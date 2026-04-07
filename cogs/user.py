import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID, ADMIN_CHANNEL_ID
from database import AsyncSessionLocal
from sqlalchemy import text
from logger import logger


# -----------------------------------------------
# View: 유저 목록 페이지네이션
# -----------------------------------------------
class UserListPaginationView(discord.ui.View):
    def __init__(self, pages, make_embed):
        super().__init__(timeout=60)
        self.pages = pages
        self.make_embed = make_embed
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.current), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.current), view=self)


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
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, race, tier FROM users ORDER BY created_at DESC")
            )
            users = result.fetchall()

        if not users:
            await interaction.followup.send("등록된 유저가 없습니다.", ephemeral=True)
            return

        lines = [f"{u.nickname} / {u.race} / {u.tier}" for u in users]
        pages = [lines[i:i+20] for i in range(0, len(lines), 20)]

        def make_embed(page_idx):
            embed = discord.Embed(title="📋 유저 목록", color=0x00aaff)
            embed.add_field(name="\u200b", value="\n".join(pages[page_idx]), inline=False)
            embed.set_footer(text=f"{page_idx + 1} / {len(pages)} 페이지")
            return embed

        view = UserListPaginationView(pages, make_embed)
        await interaction.followup.send(embed=make_embed(0), view=view)

    @app_commands.command(name="닉네임변경신청", description="닉네임 변경을 신청합니다 (관리자 승인 필요)")
    @app_commands.describe(nickname="변경할 닉네임")
    async def request_nickname(self, interaction: discord.Interaction, nickname: str):
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.followup.send("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.", ephemeral=True)
            return

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("INSERT INTO change_requests (type, discord_id, old_value, new_value, channel_id) VALUES ('nickname', :discord_id, :old_value, :new_value, :channel_id) RETURNING id"),
                    {"discord_id": interaction.user.id, "old_value": user.nickname, "new_value": nickname, "channel_id": interaction.channel_id}
                )
                req_id = result.fetchone().id
                await session.commit()

            admin_channel = await self.bot.fetch_channel(ADMIN_CHANNEL_ID)
            embed = discord.Embed(title="📝 닉네임 변경 신청", color=0xffa500)
            embed.add_field(name="신청자", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="현재 닉네임", value=user.nickname, inline=False)
            embed.add_field(name="변경 닉네임", value=nickname, inline=False)

            from cogs.admin import NicknameApprovalView
            message = await admin_channel.send(embed=embed, view=NicknameApprovalView())

            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE change_requests SET message_id = :message_id WHERE id = :id"),
                    {"message_id": message.id, "id": req_id}
                )
                await session.commit()

            logger.info(f"[닉네임변경신청] {interaction.user} | {user.nickname} → {nickname}")
            await interaction.followup.send(f"{interaction.user.mention}({user.nickname})님의 닉네임 변경 신청이 완료됐습니다. 관리자 승인을 기다려주세요.")
        except Exception as e:
            logger.error(f"[닉네임변경신청 오류] {e}")
            await interaction.followup.send("오류가 발생했습니다. 관리자에게 문의해주세요.", ephemeral=True)

    @app_commands.command(name="종족변경신청", description="종족 변경을 신청합니다 (관리자 승인 필요)")
    @app_commands.choices(race=[
        app_commands.Choice(name="테란", value="T"),
        app_commands.Choice(name="저그", value="Z"),
        app_commands.Choice(name="프로토스", value="P"),
    ])
    async def request_race(self, interaction: discord.Interaction, race: str):
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT nickname, race FROM users WHERE discord_id = :discord_id"),
                {"discord_id": interaction.user.id}
            )
            user = result.fetchone()

        if not user:
            await interaction.followup.send("등록된 유저가 아닙니다. `/유저등록`을 먼저 해주세요.", ephemeral=True)
            return

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("INSERT INTO change_requests (type, discord_id, old_value, new_value, channel_id) VALUES ('race', :discord_id, :old_value, :new_value, :channel_id) RETURNING id"),
                    {"discord_id": interaction.user.id, "old_value": user.race, "new_value": race, "channel_id": interaction.channel_id}
                )
                req_id = result.fetchone().id
                await session.commit()

            admin_channel = await self.bot.fetch_channel(ADMIN_CHANNEL_ID)
            embed = discord.Embed(title="📝 종족 변경 신청", color=0xffa500)
            embed.add_field(name="신청자", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="닉네임", value=user.nickname, inline=False)
            embed.add_field(name="현재 종족", value=user.race, inline=False)
            embed.add_field(name="변경 종족", value=race, inline=False)

            from cogs.admin import RaceApprovalView
            message = await admin_channel.send(embed=embed, view=RaceApprovalView())

            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE change_requests SET message_id = :message_id WHERE id = :id"),
                    {"message_id": message.id, "id": req_id}
                )
                await session.commit()

            logger.info(f"[종족변경신청] {interaction.user} | {user.race} → {race}")
            await interaction.followup.send(f"{interaction.user.mention}({user.nickname})님의 종족 변경 신청이 완료됐습니다. 관리자 승인을 기다려주세요.")
        except Exception as e:
            logger.error(f"[종족변경신청 오류] {e}")
            await interaction.followup.send("오류가 발생했습니다. 관리자에게 문의해주세요.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(User(bot), guilds=[GUILD_ID])
