import asyncio
import os
import logging
from typing import Any, Dict
import discord
import yaml
import datetime
import zoneinfo
from mtbridge import MeshtasticBridge, IncomingMeshtasticTextMessage

# Logging Setup
if bool(os.getenv("DEBUG", False)):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LongmontBot")


class JoinBot(discord.Bot):
    def load_config(self, config_file: str):
        with open(config_file, 'r') as config:
            self.config = yaml.load(config, Loader=yaml.SafeLoader)
        logger.info(f'Loaded configuration from [{config}]')
        password = os.getenv('MQTT_PASSWORD', None)
        if password:
            address = self.config['mqtt']['address']
            port = self.config['mqtt']['port']
            username = self.config['mqtt']['username']
            self.bridge = MeshtasticBridge(address=address, username=username, password=password, port=int(port))
            self.bridge.start_handling()
            self.mesh_links = {}
            for link in self.config['mqtt']['links']:
                self.mesh_links[link['mesh']] = link['discord']
            self.loop.call_later(5, self.lora_message_handler)

    def generate_lora_embed(self, message: IncomingMeshtasticTextMessage):
        discord_embed = discord.Embed(
            color=0x02c966,
            description=message.messsage,
            title=f'{message.channel}: {message.userinfo.get("long_name",message.userinfo.get("uid","Unknown Sender"))}'
        )
        discord_embed.set_footer(text='Meshtastic Message Bridge')
        for field in ('hardware', 'battery', 'altitude'):
            if field in message.userinfo.keys():
                discord_embed.add_field(
                        name=field.capitalize(),
                        value=message.userinfo.get(field),
                        inline=True
                    )
        if 'pos_at_time' in message.userinfo.keys():
            discord_embed.add_field(
                    name="Position",
                    value=f"{round(float(message.userinfo.get('latitude')),2)},{round(float(message.userinfo.get('longitude')),2)} @ {datetime.datetime.fromtimestamp(message.userinfo.get('pos_at_time'),tz=zoneinfo.ZoneInfo('America/Denver')).isoformat(timespec='minutes')}",
                    inline=False
                )
            discord_embed.url = f"https://www.google.com/maps/search/?api=1&query={message.userinfo.get('latitude')}%2C{message.userinfo.get('longitude')}"
        discord_embed.timestamp = datetime.datetime.fromtimestamp(int(message.timestamp))
        return discord_embed

    def lora_message_handler(self):
        for message in self.bridge.get_incoming_messages():
            if message.channel in self.mesh_links.keys():
                channel = self.get_channel(self.mesh_links[message.channel])
                embed = self.generate_lora_embed(message)
                self.loop.create_task(channel.send(embed=embed))
        self.loop.call_later(5, self.lora_message_handler)

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
