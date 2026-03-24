```sh
pip install -r requirements.txt
```

```sh
python3 -m venv venv # 가상환경 생성
source venv/bin/activate # 가상환경 활성화
pip install -r requirements.txt # 가상환경 내 라이브러리 설치
```

```sh
# 서비스 등록
sudo cp /home/ubuntu/badak-bot/badak-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable badak-bot
sudo systemctl start badak-bot
```

```sh
# !명령어
@bot.command(name="핑")
async def ping(ctx):
    await ctx.send(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")

# /명령어
@bot.tree.command(name="핑", description="봇 응답속도를 확인합니다")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")
```