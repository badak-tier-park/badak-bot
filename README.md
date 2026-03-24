```sh
pip install -r requirements.txt
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