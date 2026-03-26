import discord
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))
