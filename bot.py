import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class P4ND0Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='$', description=description, intents=intents)

    async def setup_hook(self):
        # Load cogs
        cogs = ['cogs.utility', 'cogs.characters', 'cogs.warhorn']
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"Loaded extension: {cog}")
            except Exception as e:
                print(f"Failed to load extension {cog}: {e}")
        
        # Sync application slash commands globally
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = P4ND0Bot()

if __name__ == '__main__':
    bot.run(discord_token)