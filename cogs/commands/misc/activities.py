import traceback

import discord
from discord.ext import commands
import cogs.utils.context as context
import cogs.utils.permission_checks as permissions
from discordTogether import DiscordTogether
from dotenv import find_dotenv, load_dotenv
import os
load_dotenv(find_dotenv())
token = os.environ.get("BOTTY_TOKEN")

class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.togetherControl = DiscordTogether(bot)

    @commands.command(name="activity")
    @commands.guild_only()
    @permissions.mod_and_up()
    async def youtube(self, ctx: context.Context, *, message: str):
        """allows you to start discord activities.

        Example usage
        -------------
        !youtube

        Parameters
        ----------
        activity : str
            the activity to start, selectable from, poker, youtube, betrayal,fishing and chess
        
        """
        
        await ctx.send_success(message, delete_after=5)
    @commands.command()
    async def youtube(self, ctx):
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'youtube')
        await ctx.send(f"Click the blue link!\n{link}")
    @commands.command()
    async def poker(self, ctx):
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'poker')
        await ctx.send(f"Click the blue link!\n{link}")
    @commands.command()
    async def chess(self, ctx):
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'chess')
        await ctx.send(f"Click the blue link!\n{link}")
    @commands.command()
    async def betrayal(self, ctx):
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'betrayal')
        await ctx.send(f"Click the blue link!\n{link}")
    @commands.command()
    async def fishing(self, ctx):
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'fishing')
        await ctx.send(f"Click the blue link!\n{link}")

    

    
    
    
    
    @activity.error
    async def info_error(self, ctx: context.Context, error):
        await ctx.message.delete(delay=5)
        if (isinstance(error, commands.MissingRequiredArgument)
            or isinstance(error, permissions.PermissionsFailure)
            or isinstance(error, commands.BadArgument)
            or isinstance(error, commands.BadUnionArgument)
            or isinstance(error, commands.MissingPermissions)
            or isinstance(error, commands.BotMissingPermissions)
            or isinstance(error, commands.MaxConcurrencyReached)
                or isinstance(error, commands.NoPrivateMessage)):
            await ctx.send_error(error)
        else:
            await ctx.send_error("A fatal error occured. Tell <@472331824920657940> about this.")
            traceback.print_exc()


def setup(bot):
    bot.add_cog(activity(bot))
