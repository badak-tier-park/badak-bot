```sh
pip install -r requirements.txt
```

---

### ↓↓↓ 리눅스 환경 ↓↓↓

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

---

### Scopes

| Scopes | Description |
| ------ | ----------- |
| `bot`  | 봇으로서 서버에 참여 가능

### Bot Permissions

| Permissions                     | Description |
| ------------------------------- | ----------- |
| `Read Messages / View Channels` | 채널 보기
| `Send Messages`                 | 메시지 전송
| `Manage Roles`                  | 역할 부여/제거

<br>

### 명령어

```py
# !명령어
@bot.command(name="핑")
async def ping(ctx):
    await ctx.send(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")

# /명령어
@bot.tree.command(name="핑", description="봇 응답속도를 확인합니다")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"퐁! 지연시간: {round(bot.latency * 1000)}ms")
```

<br>

### asyncio

Python 비동기 처리 라이브러리이다.  
디스코드 봇은 동시에 여러 일을 처리해야 한다.  

`유저A가 /핑 입력`  
`유저B가 /전적 입력  ← 외부 API 호출 (시간 걸림)`  
`유저C가 /핑 입력`  

일반적인 코드(동기)라면 `유저B`의 로직이 끝날 때까지 `유저C`는 대기해야 한다.

`asyncio`를 쓰면 `유저B`가 API 응답 기다리는 동안 `유저C` 요청을 먼저 처리할 수 있다.

<br>

### ephemeral=True

명령어를 실행한 사람만 볼 수 있게 하는 옵션(채널 도배 방지)

<br>