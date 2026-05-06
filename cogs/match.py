import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text
from database import AsyncSessionLocal
from logger import logger
import uuid

async def map_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    search_term = f"%{current}%"
    query = """
        SELECT name, aliases 
        FROM maps 
        WHERE name ILIKE :search
           OR EXISTS (
               SELECT 1 FROM unnest(aliases) AS a WHERE a ILIKE :search
           )
        ORDER BY name ASC
        LIMIT 25
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(query), {"search": search_term})
        maps = result.fetchall()
        
    return [app_commands.Choice(name=m.name, value=m.name) for m in maps]

async def user_search_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    search_term = f"%{current}%"
    query = """
        SELECT nickname, race, tier, aliases 
        FROM users 
        WHERE nickname ILIKE :search
           OR EXISTS (
               SELECT 1 FROM unnest(aliases) AS a WHERE a ILIKE :search
           )
        ORDER BY tier ASC, nickname ASC
        LIMIT 25
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(query), {"search": search_term})
        users = result.fetchall()
        
    choices = []
    # Avoid showing self if we can fetch user's own nickname
    # But for a robust system, we check their discord_id
    # We didn't fetch discord_id in query, so we'll just show everyone or filter loosely
    for u in users:
        matched_alias = None
        if current and u.aliases:
            for alias in u.aliases:
                if current.lower() in alias.lower():
                    matched_alias = alias
                    break
        
        display = f"{u.nickname} ({u.race}/{u.tier})"
        if matched_alias and current.lower() not in u.nickname.lower():
            display += f" - 별칭: {matched_alias}"
            
        choices.append(app_commands.Choice(name=display, value=u.nickname))
        
    return choices[:25]


class MatchConfirmView(discord.ui.View):
    def __init__(self, author_id: int, winner_name: str, loser_name: str, map_name: str):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.winner_name = winner_name
        self.loser_name = loser_name
        self.map_name = map_name

    @discord.ui.button(label="확정", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
            return

        try:
            async with AsyncSessionLocal() as session:
                w_res = await session.execute(text("SELECT nickname, race FROM users WHERE nickname = :name"), {"name": self.winner_name})
                winner_row = w_res.fetchone()
                l_res = await session.execute(text("SELECT nickname, race FROM users WHERE nickname = :name"), {"name": self.loser_name})
                loser_row = l_res.fetchone()
                
                if not winner_row or not loser_row:
                    await interaction.response.send_message("❌ 유저 정보를 찾을 수 없습니다.", ephemeral=True)
                    return

                insert_q = """
                    INSERT INTO games (
                        discord_id, 
                        played_at, 
                        map_name, 
                        game_duration_seconds, 
                        winner_name, 
                        winner_race, 
                        loser_name, 
                        loser_race, 
                        winner_apm, 
                        loser_apm, 
                        replay_file
                    ) VALUES (
                        :discord_id,
                        NOW(),
                        :map_name,
                        0,
                        :w_name,
                        :w_race,
                        :l_name,
                        :l_race,
                        0,
                        0,
                        :replay_file
                    )
                """
                await session.execute(text(insert_q), {
                    "discord_id": interaction.user.id,
                    "map_name": self.map_name,
                    "w_name": winner_row.nickname,
                    "w_race": winner_row.race,
                    "l_name": loser_row.nickname,
                    "l_race": loser_row.race,
                    "replay_file": f"manual_entry_{uuid.uuid4().hex}"
                })
                await session.commit()
            
            embed = discord.Embed(title="⚔️ 수기 경기 결과 등록 완료", color=discord.Color.blue())
            embed.add_field(name="🏆 승리", value=f"{winner_row.nickname} ({winner_row.race})", inline=True)
            embed.add_field(name="💀 패배", value=f"{loser_row.nickname} ({loser_row.race})", inline=True)
            embed.add_field(name="🗺️ 맵", value=self.map_name, inline=True)
            embed.set_footer(text=f"신고: {interaction.user.display_name}")
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            self.stop()
            
        except Exception as e:
            logger.error(f"[경기등록 확정 오류] {e}")
            await interaction.response.send_message(f"❌ 데이터베이스 오류가 발생했습니다.", ephemeral=True)


    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ 경기 등록이 취소되었습니다.", embed=None, view=None)
        self.stop()


class MatchBatchModal(discord.ui.Modal, title='다중 경기 일괄 입력'):
    content = discord.ui.TextInput(
        label='내용 (예: 투혼 승 / 파이썬 패)',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, reporter_id: int, opponent_name: str, me_name: str):
        super().__init__()
        self.reporter_id = reporter_id
        self.opponent_name = opponent_name
        self.me_name = me_name
        self.content.placeholder = '[예시]\n투혼 승\n파이썬 패\n\n(한 줄에 한 경기씩 입력, 맵 별칭도 자동 검색됨)'

    async def on_submit(self, interaction: discord.Interaction):
        text_content = self.content.value
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        
        if not lines:
            await interaction.response.send_message("❌ 입력된 내용이 없습니다.", ephemeral=True)
            return

        valid_matches = []
        errors = []
        
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(text("SELECT nickname, race FROM users WHERE nickname IN (:my_n, :opp_n)"), 
                                            {"my_n": self.me_name, "opp_n": self.opponent_name})
                users = {row.nickname: row for row in res.fetchall()}
                
                me_row = users.get(self.me_name)
                opp_row = users.get(self.opponent_name)
                
                if not me_row or not opp_row:
                    await interaction.response.send_message("❌ 본인 또는 상대방의 유저 정보를 찾을 수 없습니다.", ephemeral=True)
                    return

                res = await session.execute(text("SELECT name, aliases FROM maps"))
                maps_db = res.fetchall()

                for line in lines:
                    parts = line.rsplit(maxsplit=1)
                    if len(parts) != 2:
                        errors.append(f"❌ 형식 오류: '{line}' (예: 투혼 승)")
                        continue
                        
                    map_input, result_input = parts[0], parts[1]
                    
                    r_str = result_input.replace('승리', '승').replace('패배', '패').upper()
                    if r_str in ['승', 'W', 'WIN']: result = 'WIN'
                    elif r_str in ['패', 'L', 'LOSS']: result = 'LOSS'
                    else:
                        errors.append(f"❌ 승패 오류: '{line}' ('승' 또는 '패'로 입력해주세요)")
                        continue

                    found_map = None
                    exact_matches = []
                    fuzzy_matches = []
                    
                    possibility_names = []
                    mapping = {}
                    
                    for m in maps_db:
                        mapping[m.name.lower()] = m.name
                        possibility_names.append(m.name.lower())
                        
                        if map_input.lower() == m.name.lower():
                            exact_matches.append(m.name)
                        elif m.aliases and any(map_input.lower() == a.lower() for a in m.aliases):
                            exact_matches.append(m.name)
                            
                        if m.aliases:
                            for a in m.aliases:
                                mapping[a.lower()] = m.name
                                possibility_names.append(a.lower())

                    if exact_matches:
                        found_map = exact_matches[0]
                    else:
                        for lower_val, real_name in mapping.items():
                            if map_input.lower() in lower_val:
                                fuzzy_matches.append(real_name)
                        
                        if len(set(fuzzy_matches)) == 1:
                            found_map = fuzzy_matches[0]
                        elif len(set(fuzzy_matches)) > 1:
                            names = ", ".join(set(fuzzy_matches))
                            errors.append(f"❓ '{map_input}' 맵 이름이 모호합니다: {names} 중 하나로 정확히 입력해주세요.")
                            continue

                    # Typo correction (Levenshtein) using difflib if STILL not found
                    if not found_map:
                        import difflib
                        close = difflib.get_close_matches(map_input.lower(), possibility_names, n=1, cutoff=0.6)
                        if close:
                            found_map = mapping[close[0]]
                        else:
                            errors.append(f"❌ '{map_input}' 이라는 맵을 찾을 수 없습니다. 오타일 경우 최대한 비슷하게 적어주세요.")
                            continue

                    valid_matches.append({
                        'map': found_map,
                        'result': result
                    })

                if errors:
                    err_msg = "\n".join(errors)
                    if len(err_msg) > 1500:
                        err_msg = err_msg[:1500] + "\n...(생략)"
                    msg = f"⛔ **처리 실패 (일부 오류 발생)**\n\n{err_msg}\n\n다시 확인하시고 깔끔하게 줄바꿈하여 입력해주세요."
                    await interaction.response.send_message(msg, ephemeral=True)
                    return
                
                processed_count = 0
                desc = ""
                for m in valid_matches:
                    if m['result'] == 'WIN':
                        winner, loser = me_row, opp_row
                        res_str = "승리"
                    else:
                        winner, loser = opp_row, me_row
                        res_str = "패배"
                    
                    insert_q = """
                        INSERT INTO games (
                            discord_id, played_at, map_name, game_duration_seconds, 
                            winner_name, winner_race, loser_name, loser_race, 
                            winner_apm, loser_apm, replay_file
                        ) VALUES (
                            :u_id, NOW(), :map, 0,
                            :w_n, :w_r, :l_n, :l_r,
                            0, 0, :replay_file
                        )
                    """
                    await session.execute(text(insert_q), {
                        "u_id": self.reporter_id,
                        "map": m['map'],
                        "w_n": winner.nickname,
                        "w_r": winner.race,
                        "l_n": loser.nickname,
                        "l_r": loser.race,
                        "replay_file": f"manual_entry_{uuid.uuid4().hex}"
                    })
                    desc += f"- **{m['map']}**: {res_str}\n"
                    processed_count += 1
                
                await session.commit()
                
            embed = discord.Embed(title=f"✅ {processed_count}건 경기 일괄 등록 완료", description=f"vs **{self.opponent_name}**\n\n{desc}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"[다중경기등록 처리 오류] {e}")
            await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


class MatchCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="경기등록", description="1:1 수기 경기 결과를 등록합니다.")
    @app_commands.describe(result="자신의 승패 여부", opponent="상대방 닉네임", map_name="플레이한 맵")
    @app_commands.choices(result=[
        app_commands.Choice(name="승리", value="WIN"),
        app_commands.Choice(name="패배", value="LOSS")
    ])
    @app_commands.autocomplete(opponent=user_search_autocomplete, map_name=map_autocomplete)
    async def register_match(self, interaction: discord.Interaction, result: app_commands.Choice[str], opponent: str, map_name: str):
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT nickname FROM users WHERE discord_id = :d_id"), {"d_id": interaction.user.id})
            me = res.fetchone()
            if not me:
                await interaction.followup.send("❌ 먼저 본인을 등록해주세요. (`/유저등록`)", ephemeral=True)
                return
            
            o_res = await session.execute(text("SELECT nickname FROM users WHERE nickname = :opp"), {"opp": opponent})
            opp_row = o_res.fetchone()
            if not opp_row:
                await interaction.followup.send(f"❌ 상대방('{opponent}')을 구별할 수 없습니다. 자동완성 목록에서 선택해주세요.", ephemeral=True)
                return
            
            if me.nickname == opp_row.nickname:
                await interaction.followup.send("❌ 자기 자신과는 기록을 남길 수 없습니다.", ephemeral=True)
                return

            m_res = await session.execute(text("SELECT name FROM maps WHERE name = :m_name"), {"m_name": map_name})
            if not m_res.fetchone():
                await interaction.followup.send(f"❌ 맵('{map_name}')을 찾을 수 없습니다. 자동완성 목록에서 선택해주세요.", ephemeral=True)
                return
        
        if result.value == 'WIN':
            winner = me.nickname
            loser = opp_row.nickname
        else:
            winner = opp_row.nickname
            loser = me.nickname

        embed = discord.Embed(title="⚔️ 결과 기록 확인", description="아래 전적이 맞다면 '확정'을 눌러주세요.", color=discord.Color.orange())
        embed.add_field(name="🏆 승리", value=winner, inline=True)
        embed.add_field(name="💀 패배", value=loser, inline=True)
        embed.add_field(name="🗺️ 맵", value=map_name, inline=True)

        view = MatchConfirmView(interaction.user.id, winner, loser, map_name)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


    @app_commands.command(name="다중경기등록", description="여러 판의 경기 결과를 한 번에 입력합니다.")
    @app_commands.describe(opponent="상대방 닉네임 (별칭 호환)")
    @app_commands.autocomplete(opponent=user_search_autocomplete)
    async def register_batch_match(self, interaction: discord.Interaction, opponent: str):
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT nickname FROM users WHERE discord_id = :d_id"), {"d_id": interaction.user.id})
            me = res.fetchone()
            if not me:
                await interaction.response.send_message("❌ 먼저 본인을 등록해주세요. (`/유저등록`)", ephemeral=True)
                return
            
            o_res = await session.execute(text("SELECT nickname, race FROM users WHERE nickname = :opp"), {"opp": opponent})
            opp_row = o_res.fetchone()
            if not opp_row:
                await interaction.response.send_message(f"❌ 상대방('{opponent}')을 찾을 수 없습니다.", ephemeral=True)
                return
            
            if me.nickname == opp_row.nickname:
                await interaction.response.send_message("❌ 자기 자신과는 경기를 할 수 없습니다.", ephemeral=True)
                return
                
        await interaction.response.send_modal(MatchBatchModal(interaction.user.id, opp_row.nickname, me.nickname))

import config

async def setup(bot: commands.Bot):
    await bot.add_cog(MatchCommands(bot), guilds=[config.GUILD_ID])
