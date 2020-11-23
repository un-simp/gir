import discord
from discord.ext import commands
import cogs.utils.logs as logging
from data.case import Case
import traceback
import typing
import datetime
import pytimeparse

class ModActions(commands.Cog):
    def __init__(self, bot):    
        self.bot = bot

    @commands.guild_only()
    @commands.command(name="warn")
    async def warn(self, ctx, user: discord.Member, points: int, *, reason: str = "No reason."):
        await ctx.message.delete()

        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if points < 1:
            raise commands.BadArgument(message="Points can't be lower than 1.")
        if user.top_role >= ctx.author.top_role:
            raise commands.BadArgument(message=f"{user}'s top role is the same or higher than yours!")
        
        guild = self.bot.settings.guild()
        
        case = Case(
            _id = guild.case_id,
            _type = "WARN",
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
            punishment_points=points
        )

        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)
        await self.bot.settings.inc_points(user.id, points)

        results = await self.bot.settings.user(user.id)
        cur_points = results.warn_points
        log = await logging.prepare_warn_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        if public_chan:
            await public_chan.send(embed=log)  

        log.add_field(name="Current points", value=cur_points, inline=True)
        await ctx.send(embed=log)

        if cur_points >= 600:
            await ctx.invoke(self.ban, user=user, reason="600 or more points reached")
        elif cur_points >= 400 and not results.was_warn_kicked:
            await self.bot.settings.set_warn_kicked(user.id)
            
            try:
                await user.send("You were kicked from r/Jailbreak for reaching 400 or more points.", embed=log)
            except Exception:
                pass
            
            await ctx.invoke(self.kick, user=user, reason="400 or more points reached")
        else:
            try:
                await user.send("You were warned in r/Jailbreak.", embed=log)      
            except Exception:
                pass
    
    @commands.guild_only()
    @commands.command(name="liftwarn")
    async def liftwarn(self, ctx, user: discord.Member, case_id: int, *, reason: str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if user.top_role >= ctx.author.top_role:
            raise commands.BadArgument(message=f"{user}'s top role is the same or higher than yours!")

        cases = await self.bot.settings.get_case(user.id, case_id)
        case = cases.cases.filter(_id=case_id).first()
        
        if case is None:
            raise commands.BadArgument(message=f"{user} has no case with ID {case_id}")
        
        if case._type != "WARN":
            raise commands.BadArgument(message=f"{user}'s case with ID {case_id} is not a warn case.")
        
        if case.lifted:
            raise commands.BadArgument(message=f"Case with ID {case_id} already lifted.")
        
        case.lifted = True
        case.lifted_reason = reason
        case.lifted_by_tag = str(ctx.author)
        case.lifted_by_id = ctx.author.id
        case.lifted_date = datetime.datetime.now()
        cases.save()

        await self.bot.settings.inc_points(user.id, -1 * case.punishment_points)

        log = await logging.prepare_liftwarn_log(ctx, user, case)
        try:
            await user.send("Your warn was lifted in r/Jailbreak.", embed=log)      
        except Exception:
            pass
        
        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        if public_chan:
            await public_chan.send(embed=log)  
        await ctx.send(embed=log)
    
    @commands.guild_only()
    @commands.command(name="kick")
    async def kick(self, ctx, user: discord.Member, *, reason: str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if user.top_role >= ctx.author.top_role:
            raise commands.BadArgument(message=f"{user}'s top role is the same or higher than yours!")
        
        case = Case(
            _id = self.bot.settings.guild().case_id,
            _type = "KICK",
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
        )
        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)

        log = await logging.prepare_kick_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        await public_chan.send(embed=log)
        await ctx.send(embed=log)
        
        try:
            await user.send("You were kicked from r/Jailbreak", embed=log)
        except Exception:
            pass

        await user.kick(reason=reason)
    
    @commands.guild_only()
    @commands.command(name="ban")
    async def ban(self, ctx, user: typing.Union[discord.Member, int], *, reason: str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if isinstance(user, discord.Member):
            if user.top_role >= ctx.author.top_role:
                raise commands.BadArgument(message=f"{user}'s top role is the same or higher than yours!")
        
        if isinstance(user, int):
            try:
                user = await self.bot.fetch_user(user)
            except discord.NotFound:
                raise commands.BadArgument(f"Couldn't find user with ID {user}")
        

        case = Case(
            _id = self.bot.settings.guild().case_id,
            _type = "BAN",
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
        )
        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)

        log = await logging.prepare_ban_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        await public_chan.send(embed=log)
        await ctx.send(embed=log)
        
        try:
            await user.send("You were banned from r/Jailbreak", embed=log)
        except Exception:
            pass
        
        if isinstance(user, discord.Member):
            await user.ban(reason=reason)
        else:
            await ctx.guild.ban(discord.Object(id=user.id))

    @commands.guild_only()
    @commands.command(name="unban")
    async def unban(self, ctx, user: int, *, reason: str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if isinstance(user, discord.Member):
            if user.top_role >= ctx.author.top_role:
                raise commands.BadArgument(message=f"{user}'s top role is the same or higher than yours!")
        
        try:
            user = await self.bot.fetch_user(user)
        except discord.NotFound:
            raise commands.BadArgument(f"Couldn't find user with ID {user}")
        
        try:
            await ctx.guild.unban(discord.Object(id=user.id))
        except discord.NotFound:
            raise commands.BadArgument(f"{user} is not banned.")
        
        case = Case(
            _id = self.bot.settings.guild().case_id,
            _type = "UNBAN",
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
        )
        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)

        log = await logging.prepare_unban_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        await public_chan.send(embed=log)
        await ctx.send(embed=log)
                

    @commands.guild_only()
    @commands.command(name="purge")
    async def purge(self, ctx, limit: int = 0):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        if limit <= 0:
            raise commands.BadArgument("Number of messages to purge must be greater than 0")
        await ctx.channel.purge(limit=limit)
        await ctx.send(f'Purged {limit} messages.')
    
    @commands.guild_only()
    @commands.command(name="mute")
    async def mute(self, ctx, user:discord.Member, dur:str, *, reason : str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        
        delta = pytimeparse.parse(dur)
        if delta is None:
            raise commands.BadArgument("Failed to parse time duration.")

        time = datetime.datetime.now() + datetime.timedelta(seconds=delta)
        
        mute_role = self.bot.settings.guild().role_mute
        mute_role = ctx.guild.get_role(mute_role)
        await user.add_roles(mute_role)        
        
        try:
            self.bot.settings.tasks.schedule_unmute(user.id, time)
        except Exception:
            raise commands.BadArgument("An error occured, this user is probably already muted")

        case = Case(
            _id = self.bot.settings.guild().case_id,
            _type = "MUTE",
            until=time,
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
        )
        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)

        log = await logging.prepare_mute_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        await public_chan.send(embed=log)
        await ctx.send(embed=log)

        try:
            await user.send("You have been muted in r/Jailbreak", embed=log)
        except:
            pass

    @commands.guild_only()
    @commands.command(name="unmute")
    async def unmute(self, ctx, user:discord.Member, *, reason: str = "No reason."):
        await ctx.message.delete()
        if not self.bot.settings.permissions.hasAtLeast(ctx.guild, ctx.author, 6):
            raise commands.BadArgument("You need to be a moderator or higher to use that command.")
        
        mute_role = self.bot.settings.guild().role_mute
        mute_role = ctx.guild.get_role(mute_role)
        await user.remove_roles(mute_role)   

        try:
            self.bot.settings.tasks.cancel_unmute(user.id)
        except Exception:
            pass

        case = Case(
            _id = self.bot.settings.guild().case_id,
            _type = "UNMUTE",
            mod_id=ctx.author.id,
            mod_tag = str(ctx.author),
            reason=reason,
        )
        await self.bot.settings.inc_caseid()
        await self.bot.settings.add_case(user.id, case)

        log = await logging.prepare_unmute_log(ctx, user, case)

        public_chan = discord.utils.get(ctx.guild.channels, id=self.bot.settings.guild().channel_public)
        await public_chan.send(embed=log)
        await ctx.send(embed=log)

        try:
            await user.send("You have been unmuted in r/Jailbreak", embed=log)
        except:
            pass

    @unmute.error                    
    @mute.error
    @liftwarn.error
    @unban.error
    @ban.error
    @warn.error
    @purge.error
    @kick.error
    async def info_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await(ctx.send(error, delete_after=5))
        elif isinstance(error, commands.BadArgument):
            await(ctx.send(error, delete_after=5))
        elif isinstance(error, commands.MissingPermissions):
            await(ctx.send(error, delete_after=5))
        elif isinstance(error, commands.NoPrivateMessage):
            await(ctx.send(error, delete_after=5))
        else:
            traceback.print_exc()

def setup(bot):
    bot.add_cog(ModActions(bot))

# !warn
# !lfitwarn
# !kick
# !ban
# !mute
# !clem
# !purge