import discord
import asyncio

from . import Embed
from constants.bot import timeout_emoji


class CannotPaginate(Exception):
    pass


class HelpPages:
    def __init__(self, help_command, ctx, entries, *, dm_help=False):
        self.bot = ctx.bot
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author
        self.entries = entries
        self.prefix = help_command.clean_prefix
        self.dm_help = dm_help
        self.embed = Embed(ctx=ctx)
        self.paginating = len(entries) > 1
        self.current_page = None
        self.previous_page = None

        if ctx.guild is not None:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise CannotPaginate('Bot does not have embed links permission.')

        if not self.permissions.send_messages:
            raise CannotPaginate('Bot cannot send messages.')

        if self.paginating:
            if not self.permissions.add_reactions:
                raise CannotPaginate('Bot does not have add reactions permission.')

            if not self.permissions.read_message_history:
                raise CannotPaginate('Bot does not have Read Message History permission.')

            self.entries.append(('default', 'default', 'ℹ️', 'default'))

    # noinspection PyAttributeOutsideInit
    def get_page(self, page_name):
        for cog, description, cog_emoji, commands in self.entries:
            if cog == 'default':
                continue
            if cog == page_name:
                self.title = f'{cog} Commands'
                self.description = description
                return commands
        return None

    def get_embed(self, entries=None, *, default=False):
        if default or not entries:
            self.prepare_default_embed()
            return self.embed
        self.prepare_embed(entries)
        return self.embed

    def prepare_embed(self, entries):
        self.embed.clear_fields()
        self.embed.title = self.title
        self.embed.description = self.description

        self.embed.add_field(
            value='For more help, join the official bot support server: https://discord.gg/sbs',
            inline=False
        )

        self.embed.set_footer(text=f'Use "{self.prefix}help command" for more info on a command.')

        for entry in entries:
            signature = f'{entry.qualified_name} {entry.signature}'
            self.embed.add_field(name=signature, value=entry.short_doc or "No help given", inline=False)

    def prepare_default_embed(self):
        self.embed.clear_fields()
        self.embed.title = 'Skyblock Simplified'
        self.embed.description = 'Welcome to Skyblock Simplified, a Skyblock bot designed to streamline gameplay.'

        self.embed.add_field(
            name='React to this message with any of the emojis to view commands.',
            value='```<> signifies a required argument, while [] signifies an optional argument```',
            inline=False
        )

        for (cog, description, cog_emoji, commands) in self.entries:
            if cog == 'default':
                continue
            self.embed.add_field(
                name=f'{cog_emoji} {cog}',
                value=f'```{description}```'
            )

    # noinspection PyAttributeOutsideInit
    async def show_page(self, page_name, *, first=False):
        entries = self.get_page(page_name)
        embed = self.get_embed(entries)

        if not self.paginating:
            return await self.embed.send(dm=self.dm_help)

        if first:
            self.get_embed(default=True)
            self.message = await self.embed.send(dm=self.dm_help)
            self.current_page = 'default'
            for (cog, description, cog_emoji, commands) in self.entries:
                if cog == 'default':
                    continue
                await self.message.add_reaction(cog_emoji)
            return

        if page_name == 'default':
            embed = self.get_embed(default=True)
            await self.message.edit(embed=embed)
        else:
            await self.message.edit(embed=embed)
        for (cog, description, cog_emoji, commands) in self.entries:
            if cog == self.current_page:
                await self.message.remove_reaction(cog_emoji, self.bot.user)
            if cog == self.previous_page:
                await self.message.add_reaction(cog_emoji)

    def react_check(self, payload):
        if payload.user_id != self.author.id:
            return False

        if payload.message_id != self.message.id:
            return False

        to_check = str(payload.emoji)
        for (cog, description, cog_emoji, commands) in self.entries:
            if to_check == cog_emoji:
                self.previous_page = self.current_page
                self.current_page = cog
                return True
        return False

    async def paginate(self):
        """Actually paginate the entries and run the interactive loop if necessary."""
        first_page = self.show_page(self.entries[0][0], first=True)
        if not self.paginating:
            await first_page
        else:
            # allow us to react to reactions right away if we're paginating
            self.bot.loop.create_task(first_page)

        while self.paginating:
            try:
                payload = await self.bot.wait_for('raw_reaction_add', check=self.react_check, timeout=120.0)
            except asyncio.TimeoutError:
                self.paginating = False
                try:
                    for (cog, description, cog_emoji, commands) in self.entries:
                        await self.message.remove_reaction(cog_emoji, self.bot.user)
                    for emoji in timeout_emoji:
                        await self.message.add_reaction(emoji)
                except:
                    pass
                finally:
                    break

            try:
                await self.message.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
            except:
                pass  # can't remove it so don't bother doing so

            await self.show_page(self.current_page)