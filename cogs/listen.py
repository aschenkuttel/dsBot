from discord.ext import commands
from datetime import timedelta
from load import load
import traceback
import discord
import aiohttp
import random
import utils
import sys
import re

listener = commands.Cog.listener
error_embed = utils.error_embed


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cap = 10
        self.silenced = (commands.BadArgument,
                         aiohttp.InvalidURL,
                         discord.Forbidden,
                         utils.IngameError)

    @listener()
    async def on_message(self, message):

        if not message.guild or message.author.bot:
            return

        world = load.get_world(message.channel)
        if not world:
            return

        # Report Converter
        if message.content.__contains__("public_report"):
            file = await load.fetch_report(self.bot, message.content)
            if file is None:
                return await utils.silencer(message.add_reaction('❌'))
            try:
                await message.channel.send(file=discord.File(file, "report.png"))
                await message.delete()
            except discord.Forbidden:
                pass
            finally:
                return

        # Coord Converter
        result = re.findall(r'\d\d\d\|\d\d\d', message.content)
        if result:

            result = set(result)
            pre = load.get_prefix(message.guild.id)
            if message.content.lower().startswith(pre.lower()):
                return

            coords = [obj.replace('|', '') for obj in result]
            villages = await load.fetch_bulk(world, coords, "village", name=True)
            player_ids = [obj.player_id for obj in villages]
            players = await load.fetch_bulk(world, player_ids, dic=True)

            good = []
            for vil in villages:

                player = players.get(vil.player_id)
                if player:
                    owner = f"[{player.name}]"
                else:
                    owner = "[Barbarendorf]"

                coord = f"{vil.x}|{vil.y}"
                good.append(f"[{coord}]({vil.ingame_url}) {owner}")
                result.remove(coord)

            found = '\n'.join(good)
            lost = ','.join(result)
            if found:
                found = f"**Gefundene Koordinaten:**\n{found}"
            if lost:
                lost = f"**Nicht gefunden:**\n{lost}"
            em = discord.Embed(description=f"{found}\n{lost}")
            try:
                await message.channel.send(embed=em)
            except discord.Forbidden:
                pass
            finally:
                return

        # DS Player/Tribe Converter
        names = re.findall(r'<(.*?)>', message.clean_content)
        emojis = re.findall(r'<a?:[a-zA-Z0-9_]+:([0-9]+)>', message.content)

        for idc in emojis:
            for name in names.copy():
                if idc in name:
                    names.remove(name)

        if names:
            world = load.get_world(message.channel)
            if not world:
                return

            names = names[:10]
            parsed_msg = message.clean_content.replace("`", "")
            ds_objects = await load.fetch_bulk(world, names, name=True)
            cache = await load.fetch_bulk(world, names, 1, name=True)
            ds_objects.extend(cache)

            found_names = {}
            for dsobj in ds_objects:
                if dsobj.alone:
                    found_names[dsobj.name.lower()] = dsobj
                else:
                    found_names[dsobj.tag.lower()] = dsobj
                    found_names[dsobj.name.lower()] = dsobj

            for name in names:
                dsobj = found_names.get(name.lower())
                if not dsobj:
                    parsed_msg = parsed_msg.replace(f"<{name}>", "[Unknown]")
                    continue

                correct_name = dsobj.name if dsobj.alone else dsobj.tag
                hyperlink = f"[{correct_name}]({dsobj.ingame_url})"
                parsed_msg = parsed_msg.replace(f"<{name}>", hyperlink)

            current = message.created_at + timedelta(hours=1)
            time = current.strftime("%H:%M Uhr")
            title = f"{message.author.display_name} um {time}"
            embed = discord.Embed(description=parsed_msg)
            embed.set_author(name=title, icon_url=message.author.avatar_url)
            try:
                await message.channel.send(embed=embed)
                await message.delete()
            except discord.Forbidden:
                pass

    @listener()
    async def on_command_completion(self, ctx):
        await load.save_usage_cmd(ctx.invoked_with)

    @listener()
    async def on_command_error(self, ctx, error):
        msg, tip = None, False
        error = getattr(error, 'original', error)
        if isinstance(error, self.silenced):
            return

        elif isinstance(error, commands.CommandNotFound):
            if len(ctx.invoked_with) == ctx.invoked_with.count(ctx.prefix):
                return
            else:
                data = random.choice(load.msg["noCommand"])
                return await ctx.send(data.format(f"{ctx.prefix}{ctx.invoked_with}"))

        elif isinstance(error, commands.MissingRequiredArgument):
            msg = "Dem Command fehlt ein benötigtes Argument"
            tip = True

        elif isinstance(error, commands.NoPrivateMessage):
            msg = "Der Command ist leider nur auf einem Server verfügbar"

        elif isinstance(error, commands.PrivateMessageOnly):
            msg = "Der Command ist leider nur per private Message verfügbar"

        elif isinstance(error, utils.DontPingMe):
            msg = "Schreibe anstatt eines Pings den Usernamen oder Nickname"
            tip = True

        elif isinstance(error, utils.WorldMissing):
            msg = "Der Server hat noch keine zugeordnete Welt\n" \
                  f"Dies kann nur der Admin mit `{ctx.prefix}set world`"

        elif isinstance(error, utils.WrongChannel):
            channel = load.get_item(ctx.guild.id, "game")
            return await ctx.send(f"<#{channel}>")

        elif isinstance(error, utils.GameChannelMissing):
            msg = "Der Server hat keinen Game-Channel\n" \
                  f"Nutze `{ctx.prefix}set game` um einen festzulegen"

        elif isinstance(error, commands.NotOwner):
            msg = "Diesen Command kann nur der Bot-Owner ausführen"

        elif isinstance(error, commands.MissingPermissions):
            msg = "Diesen Command kann nur ein Server-Admin ausführen"

        elif isinstance(error, commands.CommandOnCooldown):
            raw = "Command Cooldown: Versuche es in {0:.1f} Sekunden erneut"
            msg = raw.format(error.retry_after)

        elif isinstance(error, utils.DSUserNotFound):
            name = f"Casual {ctx.world}" if ctx.world < 50 else f"der `{ctx.world}`"
            msg = f"`{error.name}` konnte auf {name} nicht gefunden werden"

        elif isinstance(error, utils.GuildUserNotFound):
            msg = f"`{error.name}` konnte nicht gefunden werden"

        elif isinstance(error, commands.BotMissingPermissions):
            msg = f"Dem Bot fehlen folgende Rechte auf diesem Server:\n" \
                  f"`{', '.join(error.missing_perms)}`"

        if msg:
            try:
                embed = error_embed(msg, ctx if tip else None)
                await ctx.send(embed=embed)
            except discord.Forbidden:
                msg = "Dem Bot fehlen benötigte Rechte: `Embed Links`"
                await ctx.safe_send(msg)

        else:
            print(f"Command Message: {ctx.message.content}")
            print("Command Error:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(Listen(bot))
