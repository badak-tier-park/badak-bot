import discord
from discord.ext import commands, tasks
from discord import app_commands
import config
from logger import logger
from database import AsyncSessionLocal
from sqlalchemy import text
import asyncio
from datetime import time, timezone, timedelta

class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.start_tasks())

    async def start_tasks(self):
        await self.bot.wait_until_ready()
        self.restart_loop()

    def restart_loop(self):
        if self.sync_nickname_loop.is_running():
            self.sync_nickname_loop.cancel()
        
        # Parse SYNC_TIME from config
        time_str = getattr(config, "SYNC_TIME", "04:00")
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            hour, minute = 4, 0
        
        # Convert KST to UTC time for datetime.time (KST is UTC+9)
        kst = timezone(timedelta(hours=9))
        target_time = time(hour=hour, minute=minute, tzinfo=kst)
        
        self.sync_nickname_loop.change_interval(time=target_time)
        self.sync_nickname_loop.start()
        logger.info(f"[스케줄러] 닉네임 동기화 루프가 매일 {time_str} (KST) 에 실행되도록 세팅 완료.")

    @tasks.loop()
    async def sync_nickname_loop(self):
        logger.info("[스케줄러] 정기 닉네임 동기화 배치 작업을 시작합니다.")
        await self._run_sync()
        
    async def _run_sync(self, interaction: discord.Interaction = None):
        guild_id_int = config.GUILD_ID.id if hasattr(config.GUILD_ID, 'id') else config.GUILD_ID
        guild = self.bot.get_guild(guild_id_int)
        
        if not guild:
            logger.error("[스케줄러] 길드 오브젝트를 찾을 수 없습니다. (GUILD_ID 확인)")
            if interaction:
                await interaction.followup.send("❌ 길드를 찾지 못해 동기화에 실패했습니다.")
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT discord_id, nickname, race, tier FROM users"))
            users = result.fetchall()

        success = 0
        skipped = 0
        failed = 0
        dm_sent = 0

        for user in users:
            target_nick = f"{user.nickname} / {user.race} / {user.tier}"
            member = guild.get_member(user.discord_id)
            if not member:
                try:
                    member = await guild.fetch_member(user.discord_id)
                except discord.NotFound:
                    skipped += 1
                    continue
                except discord.HTTPException:
                    skipped += 1
                    continue
                
            # If completely identical, skip
            if member.nick == target_nick or member.display_name == target_nick:
                skipped += 1
                continue

            # Need update
            try:
                await member.edit(nick=target_nick)
                success += 1
                logger.info(f"[배치동기화성공] {member.display_name} -> {target_nick}")
                await asyncio.sleep(1) # Rate limit 방지
            except discord.Forbidden:
                failed += 1
                logger.warning(f"[배치동기화실패] 권한 부족: {member.display_name}")
                try:
                    await member.send(f"⚠️ **닉네임 변경 안내**\n서버의 DB 정보가 업데이트되었으나, 봇의 권한 부족(서버장 등)으로 인해 자동 변경이 실패했습니다.\n원활한 서버 관리를 위해 디스코드 닉네임을 직접 **`{target_nick}`**(으)로 변경해 주시기 바랍니다.")
                    dm_sent += 1
                    await asyncio.sleep(1)
                except discord.Forbidden:
                    pass

        logger.info(f"[스케줄러] 동기화 완료: 성공 {success}, 스킵 {skipped}, 실패 {failed} (DM전송 {dm_sent})")
        if interaction:
            await interaction.followup.send(f"✅ 닉네임 강제 동기화 배치 작업 완료\n- 성공: {success}명\n- 일치/접속중아님 등으로 스킵: {skipped}명\n- 실패(권한부족): {failed}명 (DM 발송: {dm_sent}건)")
async def setup(bot: commands.Bot):
    await bot.add_cog(Schedule(bot), guilds=[config.GUILD_ID])
