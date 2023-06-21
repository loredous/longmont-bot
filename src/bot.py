import os
import logging
from typing import Dict
import discord
import yaml
from discord.ext import commands

# Logging Setup
if bool(os.getenv("DEBUG", False)):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LongmontBot")


class JoinBot(discord.Client):

    def load_config(self, config_file: str):
        with open(config_file, 'r') as config:
            self.config = yaml.load(config, Loader=yaml.SafeLoader)
        logger.info(f'Loaded configuration from [{config}]')

    def _get_guild_config(self, guild_id: int) -> Dict:
        for guild in self.config['guilds']:
            if guild['id'] == guild_id:
                return guild
        return None

    async def on_member_join(self, member: discord.Member):
        Guild = member.guild
        guild_config = self._get_guild_config(Guild.id)
        if guild_config:
            Member = member
            await Member.add_roles(Guild.get_role(guild_config['role']))
            Channel = Guild.get_channel(guild_config['intro_channel'])
            await Channel.send(f"Welcome <@{Member.id}>. Tell us a bit about yourself and we'll get you added to the server!")
            

    async def on_message(self, message: discord.Message):
        Guild = message.guild
        guild_config = self._get_guild_config(Guild.id)
        if message.channel.id == guild_config['intro_channel']:
            Member = message.author
            Role = Guild.get_role(guild_config['role'])
            if Role in Member.roles:
                await message.add_reaction("👋")

                await Member.remove_roles(Role)


if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN', None)
    config = os.getenv('BOT_CONFIG', "config.yaml")
    if token:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        bot = JoinBot(intents=intents)
        logger.info(f'Loading configuration from [{config}]')
        bot.load_config(config)
        logger.info(f'Starting Discord client with token {token[:5]}-***-{token[-5:]}')
        bot.run(token)
    else:
        logger.error('Environment variable "BOT_TOKEN" is required before starting the bot.')
