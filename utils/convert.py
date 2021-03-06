from discord.ext import commands
import utils.error as error
import re


class MemberConverter(commands.Converter):
    __slots__ = ('id', 'name', 'display_name', 'avatar_url')

    async def convert(self, ctx, arg):
        if re.match(r'<@!?([0-9]+)>$', arg):
            raise error.DontPingMe

        member = ctx.bot.get_member_by_name(ctx.guild.id, arg)
        if member is not None:
            return member

        member = await ctx.guild.query_members(arg)
        if member:
            return member[0]
        else:
            raise error.MemberNotFound(arg)


class DSConverter(commands.Converter):

    def __init__(self, ds_type=None):
        self.type = ds_type

    __slots__ = ('id', 'x', 'y', 'world', 'url', 'alone',
                 'name', 'tag', 'tribe_id', 'villages',
                 'points', 'rank', 'player', 'att_bash',
                 'att_rank', 'def_bash', 'def_rank',
                 'all_bash', 'all_rank', 'sup_bash',
                 'member', 'all_points', 'mention',
                 'guest_url', 'ingame_url', 'twstats_url')

    async def convert(self, ctx, argument):
        if self.type:
            func = getattr(ctx.bot, f"fetch_{self.type}")
            obj = await func(ctx.server, argument, name=True)
        else:
            obj = await ctx.bot.fetch_both(ctx.server, argument)

        if not obj:
            raise error.DSUserNotFound(argument)
        return obj


class WorldConverter(commands.Converter):
    __slots__ = ('server', 'speed', 'unit_speed', 'moral',
                 'config', 'lang', 'number', 'title',
                 'domain', 'icon', 'show', 'guest_url')

    async def convert(self, ctx, argument):
        argument = argument.lower()
        world = ctx.bot.worlds.get(argument)

        if world is None:
            numbers = re.findall(r'\d+', argument)
            if numbers:
                for world in ctx.bot.worlds:
                    if numbers[0] in world:
                        break

            raise error.UnknownWorld(world)

        else:
            return world


class CoordinateConverter(commands.Converter):
    def __init__(self, argument=None):
        self.x = None
        self.y = None
        if argument:
            self.x, self.y = self.parse(argument, valid=True)

    async def convert(self, ctx, argument):
        self.x, self.y = self.parse(argument)
        return self

    def parse(self, argument, valid=False):
        if valid is False:
            coord = re.match(r'\d\d\d\|\d\d\d', argument)
            if not coord:
                raise error.InvalidCoordinate
            else:
                argument = coord.string

        raw_x, raw_y = argument.split("|")
        return int(raw_x), int(raw_y)
