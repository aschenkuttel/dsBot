from discord.ext import commands
import discord


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config

    async def cog_check(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True
        else:
            raise commands.NotOwner()

    @commands.command(name="presence")
    async def presence_(self, ctx, *, args):
        await self.bot.change_presence(status=discord.Status.online,
                                       activity=discord.Game(name=args))
        await ctx.send("Presence verändert")

    @commands.command(name="reload")
    async def reload_(self, ctx, cog):
        try:
            self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send("Extension erfolgreich neu geladen")
            print("-- Extension reloaded --")
        except Exception as error:
            await ctx.send(error)

    @commands.command(name="guild_reset")
    async def guild_reset_(self, ctx, guild_id: int):
        response = self.bot.config.remove_config(guild_id)
        if response:
            msg = "Serverdaten zurückgesetzt"
        else:
            msg = "Keine zugehörige Config gefunden"
        await ctx.send(msg)

    @commands.command(name="stats")
    async def stats_(self, ctx):
        async with self.bot.ress.acquire() as conn:
            cache = await conn.fetch('SELECT * FROM usage')

        data = []
        for record in cache:
            line = f"`{record['name']}` [{record['amount']}]"
            data.append(line)

        embed = discord.Embed(description="\n".join(data))
        await ctx.send(embed=embed)

    @commands.command(name="change")
    async def change_(self, ctx, guild_id: int, item, value):
        if item.lower() not in ['prefix', 'world', 'game']:
            await ctx.send("Fehlerhafte Eingabe")
            return

        value = int(value) if item == "game" else value
        self.bot.config.update(item, value, guild_id)
        await ctx.send(f"`{item}` registriert")

    @commands.command(name="update_iron")
    async def res_(self, ctx, idc: int, iron: int):
        await self.bot.update_iron(idc, iron)
        await ctx.send(f"Dem User wurden `{iron} Eisen` hinzugefügt")

    @commands.command(name="execute")
    async def sql_(self, ctx, *, query):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute(query)
        except Exception as error:
            await ctx.send(error)

    @commands.command(name="fetch")
    async def fetch(self, ctx, *, query):
        try:
            async with self.bot.pool.acquire() as conn:
                response = await conn.fetch(query)
                await ctx.send(response)
        except Exception as error:
            await ctx.send(error)


def setup(bot):
    bot.add_cog(Owner(bot))
