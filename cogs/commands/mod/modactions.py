import datetime
import traceback

import cogs.utils.logs as logging
import cogs.utils.permission_checks as permissions
import cogs.utils.context as context
import discord
import humanize
import pytimeparse
from data.case import Case
from discord.ext import commands


class ModActions(commands.Cog):
    """This cog handles all the possible moderator actions.
    - Kick
    - Ban
    - Unban
    - Warn
    - Liftwarn
    - Mute
    - Unmute
    - Purge
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.bot_has_guild_permissions(kick_members=True, ban_members=True)
    @permissions.mod_and_up()
    @commands.command(name="warn")
    async def warn(self, ctx: context.Context, user: permissions.ModsAndAboveExternal, points: int, *, reason: str = "No reason.") -> None:
        """Warn a user (mod only)

        Example usage:
        --------------
        `!warn <@user/ID> <points> <reason (optional)>
`
        Parameters
        ----------
        user : discord.Member
            The member to warn
        points : int
            Number of points to warn far
        reason : str, optional
            Reason for warning, by default "No reason."

        """
        if points < 1:  # can't warn for negative/0 points
            raise commands.BadArgument(message="Points can't be lower than 1.")

        guild = ctx.settings.guild()

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        # prepare the case object for database
        case = Case(
            _id=guild.case_id,
            _type="WARN",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
            punishment=str(points)
        )

        # increment case ID in database for next available case ID
        await ctx.settings.inc_caseid()
        # add new case to DB
        await ctx.settings.add_case(user.id, case)
        # add warnpoints to the user in DB
        await ctx.settings.inc_points(user.id, points)

        # fetch latest document about user from DB
        results = await ctx.settings.user(user.id)
        cur_points = results.warn_points

        # prepare log embed, send to #public-mod-logs, user, channel where invoked
        log = await logging.prepare_warn_log(ctx.author, user, case)
        log.add_field(name="Current points", value=cur_points, inline=True)

        log_kickban = None
        dmed = True

        if cur_points >= 800:
            # automatically ban user if more than 600 points
            try:
                await user.send(f"You were banned from {ctx.guild.name} for reaching 800 or more points.", embed=log)
            except Exception:
                dmed = False

            log_kickban = await self.add_ban_case(ctx, user, "800 or more warn points reached.")
            await user.ban(reason="800 or more warn points reached.")

        elif cur_points >= 69420 and not results.was_warn_kicked and isinstance(user, discord.Member):
            # kick user if >= 400 points and wasn't previously kicked
            await ctx.settings.set_warn_kicked(user.id)

            try:
                await user.send(f"You were kicked from {ctx.guild.name} for reaching 400 or more points. Please note that you will be banned at 800 points.", embed=log)
            except Exception:
                dmed = False

            log_kickban = await self.add_kick_case(ctx, user, "400 or more warn points reached.")
            await user.kick(reason="400 or more warn points reached.")

        else:
            if isinstance(user, discord.Member):
                try:
                    await user.send(f"You were warned in {ctx.guild.name}. Please note that you will be kicked at 400 points and banned at 800 points.", embed=log)
                except Exception:
                    dmed = False

        # also send response in channel where command was called
        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(user.mention if not dmed else "", embed=log)

            if log_kickban:
                log_kickban.remove_author()
                log_kickban.set_thumbnail(url=user.avatar_url)
                await public_chan.send(embed=log_kickban)

    @commands.guild_only()
    @permissions.mod_and_up()
    @commands.command(name="liftwarn")
    async def liftwarn(self, ctx: context.Context, user: permissions.ModsAndAboveMember, case_id: int, *, reason: str = "No reason.") -> None:
        """Mark a warn as lifted and remove points. (mod only)

        Example usage:
        --------------
        `!liftwarn <@user/ID> <case ID> <reason (optional)>`

        Parameters
        ----------
        user : discord.Member
            User to remove warn from
        case_id : int
            The ID of the case for which we want to remove points
        reason : str, optional
            Reason for lifting warn, by default "No reason."

        """

        # retrieve user's case with given ID
        cases = await ctx.settings.get_case(user.id, case_id)
        case = cases.cases.filter(_id=case_id).first()

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        # sanity checks
        if case is None:
            raise commands.BadArgument(
                message=f"{user} has no case with ID {case_id}")
        elif case._type != "WARN":
            raise commands.BadArgument(
                message=f"{user}'s case with ID {case_id} is not a warn case.")
        elif case.lifted:
            raise commands.BadArgument(
                message=f"Case with ID {case_id} already lifted.")

        u = await ctx.settings.user(id=user.id)
        if u.warn_points - int(case.punishment) < 0:
            raise commands.BadArgument(
                message=f"Can't lift Case #{case_id} because it would make {user.mention}'s points negative.")

        # passed sanity checks, so update the case in DB
        case.lifted = True
        case.lifted_reason = reason
        case.lifted_by_tag = str(ctx.author)
        case.lifted_by_id = ctx.author.id
        case.lifted_date = datetime.datetime.now()
        cases.save()

        # remove the warn points from the user in DB
        await ctx.settings.inc_points(user.id, -1 * int(case.punishment))
        dmed = True
        # prepare log embed, send to #public-mod-logs, user, channel where invoked
        log = await logging.prepare_liftwarn_log(ctx.author, user, case)
        try:
            await user.send(f"Your warn was lifted in {ctx.guild.name}.", embed=log)
        except Exception:
            dmed = False

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(user.mention if not dmed else "", embed=log)

    @commands.guild_only()
    @permissions.mod_and_up()
    @commands.command(name="editreason")
    async def editreason(self, ctx: context.Context, user: permissions.ModsAndAboveExternal, case_id: int, *, new_reason: str) -> None:
        """Edit case reason and the embed in #public-mod-logs. (mod only)

        Example usage:
        --------------
        `!editreason <@user/ID> <case ID> <reason>`

        Parameters
        ----------
        user : discord.Member
            User to edit case of
        case_id : int
            The ID of the case for which we want to edit reason
        new_reason : str
            New reason

        """

        # retrieve user's case with given ID
        cases = await ctx.settings.get_case(user.id, case_id)
        case = cases.cases.filter(_id=case_id).first()

        new_reason = discord.utils.escape_markdown(new_reason)
        new_reason = discord.utils.escape_mentions(new_reason)

        # sanity checks
        if case is None:
            raise commands.BadArgument(
                message=f"{user} has no case with ID {case_id}")

        old_reason = case.reason
        case.reason = new_reason
        case.date = datetime.datetime.now()
        cases.save()

        dmed = True
        log = await logging.prepare_editreason_log(ctx.author, user, case, old_reason)
        if isinstance(user, discord.Member):
            try:
                await user.send(f"Your case was updated in {ctx.guild.name}.", embed=log)
            except Exception:
                dmed = False

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)

        found = False
        async with ctx.typing():
            async for message in public_chan.history(limit=200):
                if message.author.id != ctx.me.id:
                    continue
                if len(message.embeds) == 0:
                    continue
                embed = message.embeds[0]
                # print(embed.footer.text)
                if embed.footer.text == discord.Embed.Empty:
                    continue
                if len(embed.footer.text.split(" ")) < 2:
                    continue

                if f"#{case_id}" == embed.footer.text.split(" ")[1]:
                    for i, field in enumerate(embed.fields):
                        if field.name == "Reason":
                            embed.set_field_at(i, name="Reason", value=new_reason)
                            await message.edit(embed=embed)
                            found = True
        if found:
            await ctx.message.reply(f"We updated the case and edited the embed in {public_chan.mention}.", embed=log, delete_after=10)
        else:
            await ctx.message.reply(f"We updated the case but weren't able to find a corresponding message in {public_chan.mention}!", embed=log, delete_after=10)
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(user.mention if not dmed else "", embed=log)

        await ctx.message.delete(delay=10)


    @commands.guild_only()
    @permissions.mod_and_up()
    @commands.command(name="removepoints")
    async def removepoints(self, ctx: context.Context, user: permissions.ModsAndAboveMember, points: int, *, reason: str = "No reason.") -> None:
        """Remove warnpoints from a user. (mod only)

        Example usage:
        --------------
        `!removepoints <@user/ID> <points> <reason (optional)>`

        Parameters
        ----------
        user : discord.Member
            User to remove warn from
        points : int
            Amount of points to remove
        reason : str, optional
            Reason for lifting warn, by default "No reason."

        """

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        if points < 1:
            raise commands.BadArgument("Points can't be lower than 1.")

        u = await ctx.settings.user(id=user.id)
        if u.warn_points - points < 0:
            raise commands.BadArgument(
                message=f"Can't remove {points} points because it would make {user.mention}'s points negative.")

        # passed sanity checks, so update the case in DB
        # remove the warn points from the user in DB
        await ctx.settings.inc_points(user.id, -1 * points)

        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="REMOVEPOINTS",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            punishment=str(points),
            reason=reason,
        )

        # increment DB's max case ID for next case
        await ctx.settings.inc_caseid()
        # add case to db
        await ctx.settings.add_case(user.id, case)

        # prepare log embed, send to #public-mod-logs, user, channel where invoked
        log = await logging.prepare_removepoints_log(ctx.author, user, case)
        dmed = True
        try:
            await user.send(f"Your points were removed in {ctx.guild.name}.", embed=log)
        except Exception:
            dmed = False

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(user.mention if not dmed else "", embed=log)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(kick_members=True)
    @permissions.mod_and_up()
    @commands.command(name="simp")
    async def simp(self, ctx: context.Context, user: permissions.ModsAndAboveMember) -> None:
        """Kick a Simp user and tell them where to go (mod only)

        Example usage:
        --------------
        `!simp <@user/ID>`

        Parameters
        ----------
        user : discord.Member
            User to kick
        """

        reason = "You were kicked for simping"
        log = await self.add_kick_case(ctx, user, reason)

        try:
            await user.send(f"You were kicked from {ctx.guild.name}", embed=log)
        except Exception:
            pass

        await user.kick(reason=reason)

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(embed=log)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(kick_members=True)
    @permissions.mod_and_up()
    @commands.command(name="kick")
    async def kick(self, ctx: context.Context, user: permissions.ModsAndAboveMember, *, reason: str = "No reason.") -> None:
        """Kick a user (mod only)

        Example usage:
        --------------
        `!kick <@user/ID> <reason (optional)>`

        Parameters
        ----------
        user : discord.Member
            User to kick
        reason : str, optional
            Reason for kick, by default "No reason."

        """

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        log = await self.add_kick_case(ctx, user, reason)

        try:
            await user.send(f"You were kicked from {ctx.guild.name}", embed=log)
        except Exception:
            pass

        await user.kick(reason=reason)

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(embed=log)

    async def add_kick_case(self,  ctx: context.Context, user, reason):
        # prepare case for DB
        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="KICK",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )

        # increment max case ID for next case
        await ctx.settings.inc_caseid()
        # add new case to DB
        await ctx.settings.add_case(user.id, case)

        return await logging.prepare_kick_log(ctx.author, user, case)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(ban_members=True)
    @permissions.mod_and_up()
    @commands.command(name="ban")
    async def ban(self, ctx: context.Context, user: permissions.ModsAndAboveExternal, *, reason: str = "No reason."):
        """Ban a user (mod only)

        Example usage:
        --------------
        `!ban <@user/ID> <reason (optional)>`

        Parameters
        ----------
        user : typing.Union[discord.Member, int]
            The user to be banned, doesn't have to be part of the guild
        reason : str, optional
            Reason for ban, by default "No reason."

        """

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        # if the ID given is of a user who isn't in the guild, try to fetch the profile
        if ctx.guild.get_member(user.id) is None:
            async with ctx.typing():
                previous_bans = [user for _, user in await ctx.guild.bans()]
                if user in previous_bans:
                    raise commands.BadArgument("That user is already banned!")

        log = await self.add_ban_case(ctx, user, reason)

        try:
            await user.send(f"You were banned from {ctx.guild.name}", embed=log)
        except Exception:
            pass

        if isinstance(user, discord.Member):
            await user.ban(reason=reason)
        else:
            # hackban for user not currently in guild
            await ctx.guild.ban(discord.Object(id=user.id))

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(embed=log)

    async def add_ban_case(self,  ctx: context.Context, user, reason):
        # prepare the case to store in DB
        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="BAN",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            punishment="PERMANENT",
            reason=reason,
        )

        # increment DB's max case ID for next case
        await ctx.settings.inc_caseid()
        # add case to db
        await ctx.settings.add_case(user.id, case)
        # prepare log embed to send to #public-mod-logs, user and context
        return await logging.prepare_ban_log(ctx.author, user, case)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(ban_members=True)
    @permissions.mod_and_up()
    @commands.command(name="unban")
    async def unban(self, ctx: context.Context, user: permissions.ModsAndAboveExternal, *, reason: str = "No reason.") -> None:
        """Unban a user (must use ID) (mod only)

        Example usage:
        --------------
        `!unban <user ID> <reason (optional)> `

        Parameters
        ----------
        user : int
            ID of the user to unban
        reason : str, optional
            Reason for unban, by default "No reason."

        """

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        previous_bans = [user for _, user in await ctx.guild.bans()]
        if user not in previous_bans:
            raise commands.BadArgument("That user isn't banned!")

        try:
            await ctx.guild.unban(discord.Object(id=user.id), reason=reason)
        except discord.NotFound:
            raise commands.BadArgument(f"{user} is not banned.")

        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="UNBAN",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )
        await ctx.settings.inc_caseid()
        await ctx.settings.add_case(user.id, case)

        log = await logging.prepare_unban_log(ctx.author, user, case)
        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(embed=log)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_messages=True)
    @permissions.mod_and_up()
    @commands.command(name="purge")
    async def purge(self, ctx: context.Context, limit: int = 0) -> None:
        """Purge messages from current channel (mod only)

        Example usage:
        --------------
        `!purge <number of messages>`

        Parameters
        ----------
        limit : int, optional
            Number of messages to purge, must be > 0, by default 0 for error handling

        """

        if limit <= 0:
            raise commands.BadArgument(
                "Number of messages to purge must be greater than 0")
        elif limit >= 100:
            limit = 100

        msgs = await ctx.channel.history(limit=limit+1).flatten()

        await ctx.channel.purge(limit=limit+1)
        await ctx.send(f'Purged {len(msgs)} messages.', delete_after=10)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True)
    @permissions.mod_and_up()
    @commands.command(name="mute")
    async def mute(self, ctx: context.Context, user: permissions.ModsAndAboveMember, dur: str = "", *, reason: str = "No reason.") -> None:
        """Mute a user (mod only)

        Example usage:
        --------------
        `!mute <@user/ID> <duration> <reason (optional)>`

        Parameters
        ----------
        user : discord.Member
            Member to mute
        dur : str
            Duration of mute (i.e 1h, 10m, 1d)
        reason : str, optional
            Reason for mute, by default "No reason."

        """

        reason = discord.utils.escape_markdown(reason)
        reason = discord.utils.escape_mentions(reason)

        now = datetime.datetime.now()
        delta = pytimeparse.parse(dur)

        if delta is None:
            if reason == "No reason." and dur == "":
                reason = "No reason."
            elif reason == "No reason.":
                reason = dur
            else:
                reason = f"{dur} {reason}"

        mute_role = ctx.settings.guild().role_mute
        mute_role = ctx.guild.get_role(mute_role)

        if mute_role in user.roles:
            raise commands.BadArgument("This user is already muted.")

        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="MUTE",
            date=now,
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )

        if delta:
            try:
                time = now + datetime.timedelta(seconds=delta)
                case.until = time
                case.punishment = humanize.naturaldelta(
                    time - now, minimum_unit="seconds")
                ctx.tasks.schedule_unmute(user.id, time)
            except Exception:
                raise commands.BadArgument(
                    "An error occured, this user is probably already muted")
        else:
            case.punishment = "PERMANENT"

        await ctx.settings.inc_caseid()
        await ctx.settings.add_case(user.id, case)
        u = await ctx.settings.user(id=user.id)
        u.is_muted = True
        u.save()

        await user.add_roles(mute_role)

        log = await logging.prepare_mute_log(ctx.author, user, case)
        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        log.remove_author()
        log.set_thumbnail(url=user.avatar_url)
        dmed = True
        try:
            await user.send(f"You have been muted in {ctx.guild.name}", embed=log)
        except Exception:
            dmed = False

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            await public_chan.send(user.mention if not dmed else "", embed=log)


    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True)
    @permissions.mod_and_up()
    @commands.command(name="unmute")
    async def unmute(self, ctx: context.Context, user: permissions.ModsAndAboveMember, *, reason: str = "No reason.") -> None:
        """Unmute a user (mod only)

        Example usage:
        --------------
       ` !unmute <@user/ID> <reason (optional)>`

        Parameters
        ----------
        user : discord.Member
            Member to unmute
        reason : str, optional
            Reason for unmute, by default "No reason."

        """

        mute_role = ctx.settings.guild().role_mute
        mute_role = ctx.guild.get_role(mute_role)
        await user.remove_roles(mute_role)

        u = await ctx.settings.user(id=user.id)
        u.is_muted = False
        u.save()

        try:
            ctx.tasks.cancel_unmute(user.id)
        except Exception:
            pass

        case = Case(
            _id=ctx.settings.guild().case_id,
            _type="UNMUTE",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )
        await ctx.settings.inc_caseid()
        await ctx.settings.add_case(user.id, case)

        log = await logging.prepare_unmute_log(ctx.author, user, case)

        await ctx.message.reply(embed=log, delete_after=10)
        await ctx.message.delete(delay=10)

        dmed = True
        try:
            await user.send(f"You have been unmuted in {ctx.guild.name}", embed=log)
        except Exception:
            dmed = False

        public_chan = ctx.guild.get_channel(
            ctx.settings.guild().channel_public)
        if public_chan:
            log.remove_author()
            log.set_thumbnail(url=user.avatar_url)
            await public_chan.send(user.mention if not dmed else "", embed=log)

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_channels=True)
    @commands.command(name="lock")
    @permissions.admin_and_up()
    async def lock(self,  ctx: context.Context, channel: discord.TextChannel = None):
        """Lock a channel (admin only)

        Example usage
        --------------
        !lock or !lock #channel

        Parameters
        ----------
        channel : discord.TextChannel, optional
            Channel to lock
        """

        if channel is None:
            channel = ctx.channel

        if await self.lock_unlock_channel(ctx, channel, True) is not None:
            await ctx.send_success(f"Locked {channel.mention}!", delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            raise commands.BadArgument(f"{channel.mention} already locked or my permissions are wrong.")

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_channels=True)
    @permissions.admin_and_up()
    @commands.command(name="unlock")
    async def unlock(self,  ctx: context.Context, channel: discord.TextChannel = None):
        """Unlock a channel (admin only)

        Example usage
        --------------
        !unlock or !unlock #channel

        Parameters
        ----------
        channel : discord.TextChannel, optional
            Channel to unlock
        """

        if channel is None:
            channel = ctx.channel

        if await self.lock_unlock_channel(ctx, channel) is not None:
            await ctx.send_success(f"Unocked {channel.mention}!", delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            raise commands.BadArgument(f"{channel.mention} already unlocked or my permissions are wrong.")

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_channels=True)
    @permissions.admin_and_up()
    @commands.command(name="freezeable")
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def freezeable(self,  ctx: context.Context, channel: discord.TextChannel=None):
        channel = channel or ctx.channel
        if channel.id in await ctx.settings.get_locked_channels():
            raise commands.BadArgument("That channel is already lockable.")

        await ctx.settings.add_locked_channels(channel.id)
        await ctx.send_success(f"Added {channel.mention} as lockable channel!")

    @commands.bot_has_guild_permissions(manage_channels=True)
    @commands.command(name="unfreezeable")
    @permissions.admin_and_up()
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def unfreezeable(self,  ctx: context.Context, channel: discord.TextChannel=None):
        channel = channel or ctx.channel
        if channel.id not in await ctx.settings.get_locked_channels():
            raise commands.BadArgument("That channel isn't already lockable.")

        await ctx.settings.remove_locked_channels(channel.id)
        await ctx.send_success(f"Removed {channel.mention} as lockable channel!")

    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_channels=True)
    @permissions.admin_and_up()
    @commands.command(name="freeze")
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def freeze(self, ctx):
        """Freeze all channels (admin only)

        Example usage
        --------------
        !freeze
        """

        channels = await ctx.settings.get_locked_channels()
        if not channels:
            raise commands.BadArgument("No freezeable channels! Set some using `!freezeable`.")

        locked = []
        with ctx.typing():
            for channel in channels:
                channel = ctx.guild.get_channel(channel)
                if channel is not None:
                    if await self.lock_unlock_channel(ctx, channel, lock=True):
                        locked.append(channel)

        if locked:
            await ctx.send_success(f"Locked {len(locked)} channels!", delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            raise commands.BadArgument("Server is already locked or my permissions are wrong.")


    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_channels=True)
    @permissions.admin_and_up()
    @commands.command(name="unfreeze")
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def unfreeze(self, ctx):
        """Unreeze all channels (admin only)

        Example usage
        --------------
        !unfreeze
        """

        channels = await ctx.settings.get_locked_channels()
        if not channels:
            raise commands.BadArgument("No unfreezeable channels! Set some using `!freezeable`.")

        unlocked = []
        with ctx.typing():
            for channel in channels:
                channel = ctx.guild.get_channel(channel)
                if channel is not None:
                    if await self.lock_unlock_channel(ctx, channel, lock=None):
                        unlocked.append(channel)

        if unlocked:
            await ctx.send_success(f"Unlocked {len(unlocked)} channels!", delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            raise commands.BadArgument("Server is already unlocked or my permissions are wrong.")

    async def lock_unlock_channel(self,  ctx: context.Context, channel, lock=None):
        settings = ctx.settings.guild()

        default_role = ctx.guild.default_role
        member_plus = ctx.guild.get_role(settings.role_memberplus)

        default_perms = channel.overwrites_for(default_role)
        memberplus_perms = channel.overwrites_for(member_plus)

        if lock and default_perms.send_messages is None and memberplus_perms.send_messages is None:
            default_perms.send_messages = False
            memberplus_perms.send_messages = True
        elif lock is None and (not default_perms.send_messages) and memberplus_perms.send_messages:
            default_perms.send_messages = None
            memberplus_perms.send_messages = None
        else:
            return

        try:
            await channel.set_permissions(default_role, overwrite=default_perms, reason="Locked!" if lock else "Unlocked!")
            await channel.set_permissions(member_plus, overwrite=memberplus_perms, reason="Locked!" if lock else "Unlocked!")
            return True
        except Exception:
            return

    @lock.error
    @unlock.error
    @freezeable.error
    @unfreezeable.error
    @freeze.error
    @unfreeze.error
    @unmute.error
    @mute.error
    @liftwarn.error
    @unban.error
    @ban.error
    @warn.error
    @purge.error
    @kick.error
    @simp.error
    @editreason.error
    @removepoints.error
    async def info_error(self,  ctx: context.Context, error):
        await ctx.message.delete(delay=5)
        if (isinstance(error, commands.MissingRequiredArgument)
            or isinstance(error, permissions.PermissionsFailure)
            or isinstance(error, commands.BadArgument)
            or isinstance(error, commands.BadUnionArgument)
            or isinstance(error, commands.BotMissingPermissions)
            or isinstance(error, commands.MissingPermissions)
            or isinstance(error, commands.MaxConcurrencyReached)
                or isinstance(error, commands.NoPrivateMessage)):
            await ctx.send_error(error)
        else:
            await ctx.send_error(error)
            traceback.print_exc()


def setup(bot):
    bot.add_cog(ModActions(bot))
