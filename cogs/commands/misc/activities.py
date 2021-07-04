import traceback

import discord
from discord.ext import commands
import cogs.utils.context as context
import cogs.utils.permission_checks as permissions
from Discord_Together.discordtogether import DiscordTogether
from dotenv import find_dotenv, load_dotenv
import os
load_dotenv(find_dotenv())
token = os.environ.get("BOTTY_TOKEN")

class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="activity")
    @commands.guild_only()
    @permissions.mod_and_up()
    async def say(self, ctx: context.Context, *, message: str):
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
    @client.command()
    async def youtube(ctx, vc:commands.VoiceChannelConverter):
        youtube = DiscordTogether(token= token)
        invite_code = await youtube.activity(option="youtube",vc_id=vc.id)
        await ctx.send(f"https://discord.com/invite/{invite_code}")
    async def poker(ctx, vc:commands.VoiceChannelConverter):
        poker = DiscordTogether(token= token)
        invite_code = await poker.activity(option="poker",vc_id=vc.id)
        await ctx.send(f"https://discord.com/invite/{invite_code}")
    async def betrayal(ctx, vc:commands.VoiceChannelConverter):
        betrayal = DiscordTogether(token= token)
        invite_code = await betrayal.activity(option="betrayal",vc_id=vc.id)
        await ctx.send(f"https://discord.com/invite/{invite_code}")
    async def fishing(ctx, vc:commands.VoiceChannelConverter):
        fishing = DiscordTogether(token= token)
        invite_code = await fishing.activity(option="fishing",vc_id=vc.id)
        await ctx.send(f"https://discord.com/invite/{invite_code}")
    async def chess(ctx, vc:commands.VoiceChannelConverter):
        chess = DiscordTogether(token= token)
        invite_code = await chess.activity(option="chess",vc_id=vc.id)
        await ctx.send(f"https://discord.com/invite/{invite_code}")
    
    
    
    
    @say.error
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
