import discord
from discord.ext import commands
import config
from logger import logger
from database import AsyncSessionLocal
from sqlalchemy import text

class TestTicketView(discord.ui.View):
    def __init__(self, discord_id: int):
        super().__init__(timeout=None)
        self.target_id = discord_id
        # 고유 custom_id
        self.call_btn = discord.ui.Button(
            label="일반방으로 호출하기", 
            style=discord.ButtonStyle.success, 
            custom_id=f"test_call_{discord_id}"
        )
        self.call_btn.callback = self.call_callback
        self.add_item(self.call_btn)

    async def call_callback(self, interaction: discord.Interaction):
        general_channel_id = getattr(config, 'GENERAL_CHANNEL_ID', None)
        if not general_channel_id:
            await interaction.response.send_message("❌ 일반 호출 채널이 설정되지 않았습니다. `/설정`을 통해 지정해주세요.", ephemeral=True)
            return
            
        general_channel = interaction.guild.get_channel(general_channel_id)
        if not general_channel:
            await interaction.response.send_message("❌ 지정된 일반 호출 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        member = interaction.guild.get_member(self.target_id)
        if not member:
            await interaction.response.send_message("❌ 해당 유저를 서버 구성원 중에서 찾을 수 없습니다.", ephemeral=True)
            return

        await general_channel.send(f"🔔 {member.mention}님! 관리자 {interaction.user.mention}님이 테스트 참가를 요청하십니다! 접속 가능하실까요?")
        await interaction.response.send_message(f"✅ {general_channel.mention} 채널에 {member.display_name}님을 성공적으로 호출했습니다.", ephemeral=True)
        logger.info(f"[대기자호출] {interaction.user} -> {member.display_name} 에 호출 전송")


async def spawn_test_ticket(bot: commands.Bot, user_discord_id: int, nickname: str, race: str):
    """
    유저가 Test 티어가 되었을 때, 테스트방에 티켓 메시지를 생성합니다.
    """
    if not getattr(config, 'TEST_CHANNEL_ID', None):
        return False

    channel = bot.get_channel(config.TEST_CHANNEL_ID)
    if not channel:
        return False
        
    embed = discord.Embed(title="🚨 [테스트 대기]", color=0xff0000)
    embed.description = f"**대상:** <@{user_discord_id}>\n**닉네임:** {nickname}\n**종족:** {race}\n\n테스트를 진행하실 관리자분은 아래 호출 버튼을 눌러주세요."
    
    view = TestTicketView(user_discord_id)
    await channel.send(embed=embed, view=view)
    
    # 영구 View 등록
    bot.add_view(view)
    return True


class Waitlist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # 봇 재시작 시, 기존 활성화된 'Test' 티어 유저들의 버튼이 작동하도록 View를 다시 등록해줍니다.
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("SELECT discord_id FROM users WHERE tier = 'Test'"))
                waiters = result.fetchall()
            for w in waiters:
                self.bot.add_view(TestTicketView(w.discord_id))
            if waiters:
                logger.info(f"기존 테스트 대기자 {len(waiters)}명의 호출 버튼을 복구했습니다.")
        except Exception as e:
            logger.error(f"테스트 대기자 버튼 복구 중 오류 발생: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Waitlist(bot), guilds=[config.GUILD_ID])
