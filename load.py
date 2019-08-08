from PIL import Image, ImageChops
from bs4 import BeautifulSoup
from data.cogs import cmds
from data.naruto import *
import asyncpg
import datetime
import operator
import aiohttp
import asyncio
import discord
import imgkit
import random
import utils
import json
import time
import math
import os
import io
import re

options = {
    # "xvfb": "",
    "quiet": "",
    "format": "png",
    "quality": 100,
    "encoding": "UTF-8"
}

fml = '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0' \
      ' Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">' \
      '<html xmlns="http://www.w3.org/1999/xhtml">'


class Load:
    def __init__(self):
        self.config = {}
        self.worlds = []
        self.conquer = {}
        self.ress = None
        self.pool = None
        self.session = None
        self.secrets = {"CMDS": cmds, "TOKEN": TOKEN, "PRE": pre}
        self.data_loc = f"{os.path.dirname(__file__)}/data/"
        self.url_val = "https://de{}.die-staemme.de/map/ally.txt"
        self.url_set = "https://de{}.die-staemme.de/page/settings"
        self.msg = json.load(open(f"{self.data_loc}msg.json"))

    # Setup
    async def setup(self, loop):
        self.session = aiohttp.ClientSession(loop=loop)
        connections = await self.db_connect(loop)
        self.pool, self.ress = connections
        await self.fetch_worlds()
        self.config_setup()
        return self.session

    # DB Connect
    async def db_connect(self, loop):
        result = []
        database = 'tribaldata', 'userdata'
        for table in database:
            conn_data = {"host": '46.101.105.115', "port": db_port, "user": db_user,
                         "password": db_key, "database": table, "loop": loop, "max_size": 50}
            cache = await asyncpg.create_pool(**conn_data)
            result.append(cache)
        return result

    # Casual
    def casual(self, world):
        return str(world) if world > 50 else f"p{world}"

    # World Check
    def is_valid(self, world):
        return world in self.worlds

    # Config Load at Start
    def config_setup(self):
        cache = json.load(open(f"{self.data_loc}config.json"))
        data = {int(key): value for key, value in cache.items()}
        self.config.update(data)

    # Get Config Entry
    def get_config(self, guild_id, item):
        config = self.config.get(guild_id)
        if config is None:
            return
        return config.get(item)

    # Change Config Entry
    def change_config(self, guild_id, item, value):
        if guild_id not in self.config:
            self.config[guild_id] = {}
        self.config[guild_id][item] = value
        self.save_config()

    # Remove Config Entry
    def remove_config(self, guild_id, item):
        config = self.config.get(guild_id)
        if not config:
            return
        job = config.pop(item, None)
        self.save_config()
        return job

    # Get World if Main World
    def get_world(self, channel):
        con = self.config.get(channel.guild.id)
        if con is None:
            return
        main = con.get('world')
        if not main:
            return
        chan = con.get("channel")
        idc = str(channel.id)
        world = chan.get(idc, main) if chan else main
        return world

    # Get Server Main World
    def get_guild_world(self, guild, url=False):
        con = self.config.get(guild.id)
        if con is None:
            return
        world = con.get('world')
        if url and world:
            return self.casual(world)
        return world

    # Remove all World Occurences
    def remove_world(self, world):
        for guild in self.config:
            config = self.config[guild]
            if config.get('world') == world:
                config.pop('world')
            channel = config.get('channel', {})
            for ch in channel:
                if channel[ch] == world:
                    channel.pop(ch)
        self.save_config()

    # Get Server Prefix
    def pre_fix(self, guild_id):
        config = self.config.get(guild_id)
        default = self.secrets["PRE"]
        if config is None:
            return default
        return config.get("prefix", default)

    # Save Config File
    def save_config(self):
        json.dump(self.config, open(f"{self.data_loc}config.json", 'w'))

    # Ress Data Update
    async def save_user_data(self, user_id, amount):
        statement = "SELECT * FROM iron_data WHERE id = $1"
        async with self.ress.acquire() as conn:
            data = await conn.fetchrow(statement, user_id)
            statement = "INSERT INTO iron_data(id, amount) VALUES({0}, {1}) " \
                        "ON CONFLICT (id) DO UPDATE SET id={0}, amount={1}"
            new_amount = data["amount"] + amount if data else amount
            await conn.execute(statement.format(user_id, new_amount))

    # Ress Data Fetch
    async def get_user_data(self, user_id, info=False):
        statement = "SELECT * FROM iron_data"
        async with self.ress.acquire() as conn:
            data = await conn.fetch(statement)
        cache = {cur["id"]: cur["amount"] for cur in data}
        rank = "Unknown"
        sort = sorted(cache.items(), key=lambda kv: kv[1], reverse=True)
        for index, (idc, cash) in enumerate(sort):
            if idc == user_id:
                rank = index + 1
        money = cache.get(user_id, 0)
        return (money, rank) if info else money

    # Search Top
    async def get_user_top(self, amount, guild=None):
        if guild:
            raw_statement = "SELECT * FROM iron_data WHERE id IN " \
                        "({}) ORDER BY amount DESC LIMIT $1"
            member = ', '.join([str(mem.id) for mem in guild.members])
            statement = raw_statement.format(member)
        else:
            statement = "SELECT * FROM iron_data ORDER BY amount DESC LIMIT $1"
        async with self.ress.acquire() as conn:
            data = await conn.fetch(statement, amount)
        return data

    # Save Command Usage
    async def save_usage_cmd(self, cmd):
        cmd = cmd.lower()
        statement = "SELECT * FROM usage_data WHERE name = $1"
        query = "INSERT INTO usage_data(name, usage) VALUES($1, $2) " \
                "ON CONFLICT (name) DO UPDATE SET name=$1, usage=$2"
        async with self.ress.acquire() as conn:
            data = await conn.fetchrow(statement, cmd)
            new_usage = data['usage'] + 1 if data else 1
            await conn.execute(query, cmd, new_usage)

    # Return Sorted Command Usage Stats
    async def get_usage(self):
        statement = "SELECT * FROM usage_data"
        async with self.ress.acquire() as conn:
            data = await conn.fetch(statement)
        cache = {r['name']: r['usage'] for r in data}
        return sorted(cache.items(), key=operator.itemgetter(1), reverse=True)

    # Get all valid database worlds
    async def fetch_worlds(self):
        query = "SELECT table_name FROM information_schema.tables " \
                "WHERE table_schema='public' AND table_type='BASE TABLE';"
        async with self.pool.acquire() as conn:
            data = await conn.fetch(query)
        cache = [int(r['table_name'][2:]) for r in data]
        if not cache:
            return
        for world in self.worlds:
            if world not in cache:
                self.worlds.remove(world)
                self.remove_world(world)
        for world in cache:
            if world not in self.worlds:
                self.worlds.append(world)

    # Get a random player
    async def fetch_random(self, world, **kwargs):
        amount = kwargs.get("amount", 1)
        top = kwargs.get("top", 500)
        tribe = kwargs.get("tribe", False)
        least = kwargs.get("least", False)
        state = "t" if tribe else "p"

        statement = f"SELECT * FROM {state}_{world} WHERE rank < {top + 1}"
        async with self.pool.acquire() as conn:
            data = await conn.fetch(statement)

        result = []
        while len(result) < amount:
            ds_obj = random.choice(data)
            cur = [p.id for p in result]
            if ds_obj['id'] not in cur:
                if not tribe:
                    result.append(utils.Player(world, ds_obj))
                    continue
                if least and int(ds_obj['member']) > 3:
                    result.append(utils.Tribe(world, ds_obj))
                if not least:
                    result.append(utils.Tribe(world, ds_obj))

        return result[0] if amount == 1 else result

    # Search for village with coordinates or ID
    async def fetch_village(self, world, searchable, coord=False):
        if coord:
            x, y = searchable.partition("|")[0], searchable.partition("|")[2]
            statement = "SELECT * FROM v_{} WHERE x = $1 AND y = $2;"
            query, searchable = statement.format(world), [int(x), int(y)]
        else:
            statement = "SELECT * FROM v_{} WHERE id = $1;"
            query, searchable = statement.format(world), [searchable]

        async with await self.pool.acquire() as conn:
            result = await conn.fetchrow(query, *searchable)
        return utils.Village(world, result) if result else None

    # Search for player with name or ID
    async def fetch_player(self, world, searchable, name=False):
        if name:
            searchable = utils.converter(searchable, True)
            statement = "SELECT * FROM p_{} WHERE LOWER(name) = $1;"
            query = statement.format(world)
        else:
            statement = "SELECT * FROM p_{} WHERE id = $1;"
            query = statement.format(world)

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, searchable)
        return utils.Player(world, result) if result else None

    # Search for tribe with name or ID
    async def fetch_tribe(self, world, searchable, name=False):
        if name:
            searchable = utils.converter(searchable, True)
            statement = "SELECT * FROM t_{} WHERE LOWER(tag) = $1 OR LOWER(name) = $1;"
            query = statement.format(world)
        else:
            statement = "SELECT * FROM t_{} WHERE id = $1;"
            query = statement.format(world)

        async with await self.pool.acquire() as conn:
            result = await conn.fetchrow(query, searchable)
        return utils.Tribe(world, result) if result else None

    # Search for both Tribe / Player
    async def fetch_both(self, world, name):
        player = await self.fetch_player(world, name, True)
        if player:
            return player
        tribe = await self.fetch_tribe(world, name, True)
        return tribe

    # Get all Tribe Member Objects
    async def fetch_tribe_member(self, world, allys, name=False):
        if not isinstance(allys, (tuple, list)):
            allys = [allys]
        if name:
            cache = []
            for ally in allys:
                tribe = await self.fetch_tribe(world, ally, True)
                if not tribe:
                    continue
                if tribe.id not in cache:
                    cache.append(tribe.id)
        else:
            cache = allys
        result = []
        async with self.pool.acquire() as conn:
            for tribe in cache:
                statement = "SELECT * FROM p_{} WHERE tribe_id = {};"
                query = statement.format(world, tribe)
                res = await conn.fetch(query)
                for cur in res:
                    result.append(utils.Player(world, cur))
            return result

    # Get multiple Tribe Objects
    async def fetch_tribes(self, world, iterable, name=False):
        if name:
            iterable = [utils.converter(obj, True) for obj in iterable]
            statement = "SELECT * FROM t_{} WHERE ARRAY[LOWER(name), LOWER(tag)] && $1;"
            query = statement.format(world)
        else:
            iterable = [int(obj) for obj in iterable]
            statement = "SELECT * FROM t_{} WHERE id = any($1);"
            query = statement.format(world)

        async with self.pool.acquire() as conn:
            res = await conn.fetch(query, iterable)
        return [utils.Tribe(world, cur) for cur in res]

    # Get Villages from specific Player / Tribe
    async def fetch_villages(self, obj, num, world, k=None):
        res = []
        if isinstance(obj, utils.Tribe):
            statement = "SELECT * FROM p_{} WHERE tribe_id = {};"
            query = statement.format(world, obj.id)
            async with self.pool.acquire() as conn:
                cache = await conn.fetch(query)
            for cur in cache:
                res.append(cur["id"])

        else:
            res.append(obj.id)

        statement = "SELECT * FROM v_{} WHERE player IN ({})"
        if k:
            temp = " AND LEFT(CAST(x AS TEXT), 1) = '{}'" \
                   " AND LEFT(CAST(y AS TEXT), 1) = '{}'"
            statement = statement + temp.format(k[2], k[1])

        query = statement.format(world, ', '.join([str(c) for c in res]))
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query)
        random.shuffle(result)
        en_lis = result
        state = k if k else False
        if str(num).isdigit():
            en_lis = result[:int(num)]
            if len(result) < int(num):
                return obj.alone, obj.name, state, len(result)
        if len(result) == 0:
            return obj.alone, obj.name, state, len(result)
        if not len(en_lis) > 1000:
            return en_lis
        file = io.StringIO()
        file.write(f'{os.linesep}'.join(en_lis))
        file.seek(0)
        return file

    # Coord Converter
    async def coordverter(self, coord_list, world):
        result = []
        double = []
        fail = []

        for coord in coord_list:

            res = await self.fetch_village(world, coord, True)
            if not res:
                fail.append(coord) if coord not in fail else None
                continue

            if coord in double:
                continue

            url = "https://de{}.die-staemme.de/game.php?&screen=info_village&id={}"
            if res.player_id:
                player = await self.fetch_player(world, res.player_id)
                v1 = f"[{player.name}]"
            else:
                v1 = "[Barbarendorf]"
            result.append(f"[{coord}]({url.format(world, res.id)}) {v1}")
            double.append(coord)

        shit = '\n'.join(result) if result else None
        piss = ', '.join(fail) if fail else None
        found = f"**Gefundene Koordinaten:**\n{shit}" if shit else ""
        lost = f"**Nicht gefunden:**\n{piss}" if piss else ""
        return found, lost

    # Conquer Main Function
    async def conquer_feed(self, guilds):
        await self.update_conquer()
        for guild in guilds:
            world = self.get_guild_world(guild)
            if not world:
                continue
            print(world)
            channel_id = self.get_config(guild.id, "conquer")
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            tribes = self.get_config(guild.id, "filter")
            grey = self.get_config(guild.id, "bb")
            data = await self.conquer_parse(world, tribes, grey)
            if not data:
                continue

            res_cache = []
            once = data[0]
            for sen in data[1]:
                res_cache.append(sen)
                if len(res_cache) == 5:
                    embed = discord.Embed(title=once, description='\n'.join(res_cache))
                    await self.silencer(channel.send(embed=embed))
                    res_cache.clear()
                    once = ""
                    await asyncio.sleep(1)
            if res_cache:
                embed = discord.Embed(title=once, description='\n'.join(res_cache))
                await self.silencer(channel.send(embed=embed))

    async def update_conquer(self):
        for world in self.worlds:
            sec = self.get_seconds(True)
            data = await self.fetch_conquer(world, sec)
            if not data[0]:
                continue
            if data[0].startswith("<"):
                continue
            cache = []
            for line in data:
                int_list = [int(num) for num in line.split(",")]
                cache.append(int_list)
            old_data = self.conquer.get(world, [])
            old_unix = self.get_seconds(True, 1)
            result = []
            for entry in cache:
                vil_id, unix_time, new_owner, old_owner = entry
                if entry in old_data:
                    continue
                if unix_time > old_unix:
                    continue
                result.append(entry)
            self.conquer[world] = result

    # Conquer Data Download
    async def fetch_conquer(self, world, sec=3600):
        cur = time.time() - sec
        base = "http://de{}.die-staemme.de/interface.php?func=get_conquer&since={}"
        url = base.format(self.casual(world), cur)
        async with self.session.get(url) as r:
            data = await r.text("utf-8")
        return data.split("\n")

    # Parse Conquer Data
    async def conquer_parse(self, world, tribes, bb=False):
        data = self.conquer.get(world)
        if not data:
            return
        id_list = []
        res_lis = []
        if tribes:
            tribe_list = await self.fetch_tribe_member(world, tribes)
            id_list = [obj.id for obj in tribe_list]

        date = None
        for line in data:
            vil_id, unix_time, new_owner, old_owner = line
            player_idc = [new_owner, old_owner]
            if tribes and not any(idc in id_list for idc in player_idc):
                continue
            if not bb and 0 in player_idc:
                continue
            vil = await self.fetch_village(world, vil_id)
            if not vil:
                continue

            ally = self.fetch_tribe
            base = f"https://de{world}.die-staemme.de/game.php?&screen="
            res_vil = f"[{vil.x}|{vil.y}]({base}info_village&id={vil.id})"

            res_new = "Barbarendorf"
            res_old = "(Barbarendorf)"

            new = await self.fetch_player(world, new_owner)
            if new:
                url_n = f"[{new.name}]({base}info_player&id={new.id})"
                cache = await ally(world, new.tribe_id) if new.tribe_id else None
                new_tribe = f" **{cache.tag}**" if cache else f""
                res_new = f"{url_n}{new_tribe}"

            old = await self.fetch_player(world, old_owner)
            if old:
                url_o = f"[{old.name}]({base}info_player&id={old.id})"
                cache = await ally(world, old.tribe_id) if old.tribe_id else None
                old_tribe = f" **{cache.tag}**" if cache else ""
                res_old = f"von {url_o}{old_tribe}"

            now = datetime.datetime.utcfromtimestamp(int(unix_time)) + datetime.timedelta(hours=1)
            date, now = now.strftime('%d-%m-%Y'), now.strftime('%H:%M')
            res_lis.append(f"`{now}` | {res_new} adelt {res_vil} {res_old}")
        return date, res_lis

    # Recap Argument Handler
    async def re_handler(self, world, args):
        days = 7
        if ' ' not in args:
            player = await self.fetch_both(world, args)
        elif args.split(" ")[-1].isdigit():
            player = await self.fetch_both(world, ' '.join(args.split(" ")[:-1]))
            if not player:
                player = await self.fetch_both(world, args)
            else:
                days = int(args.split(" ")[-1])
        else:
            player = await self.fetch_both(world, args)
        if not player:
            raise utils.DSUserNotFound(args, world)
        return player, days

    # Village Argument Handler
    async def vil_handler(self, world, args):
        con = None
        args = args.split(" ")
        if len(args) == 1:
            name = args[0]
        elif re.match(r'[k, K]\d\d', args[-1]):
            con = args[-1]
            name = ' '.join(args[:-1])
        else:
            name = ' '.join(args)
        player = await self.fetch_both(world, name)
        if not player:
            if con:
                player = await self.fetch_both(world, f"{name} {con}")
                if not player:
                    raise utils.DSUserNotFound(name, world)
            else:
                raise utils.DSUserNotFound(name, world)
        return player, con

    # Report HTML Converting
    async def html_lover(self, raw_data):
        soup = BeautifulSoup(raw_data, 'html.parser')
        tiles = soup.body.find_all(class_="vis")
        if len(tiles) < 2:
            return

        main = tiles[1]
        main = f"{fml}<head></head>{main}"  # don't ask me why...

        css = f"{os.path.dirname(__file__)}/data/report.css"

        img = imgkit.from_string(main, False, options=options, css=css)
        return img

    # Barbershop
    async def trim(self, im):
        bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            return im.crop(bbox)

    # Main Report Func
    async def report_func(self, content):

        try:
            async with self.session.get(content) as res:
                data = await res.text()
        except (aiohttp.InvalidURL, ValueError):
            return

        img_bytes = await self.html_lover(data)
        if not img_bytes:
            return

        data_io = io.BytesIO(img_bytes)
        image = Image.open(data_io)
        img = await self.trim(image)
        img = img.crop((2, 2, img.width - 2, img.height - 2))
        file = io.BytesIO()
        img.save(file, "png")
        file.seek(0)
        return file

    # Seconds till next Hour
    def get_seconds(self, reverse=False, only=0):
        now = datetime.datetime.now()
        hours = -1 if reverse else 1
        clean = now + datetime.timedelta(hours=hours + only)
        goal_time = clean.replace(minute=0, second=0, microsecond=0)
        start_time = now.replace(microsecond=0)
        if reverse:
            goal_time, start_time = start_time, goal_time
        goal = (goal_time - start_time).seconds
        return goal if not only else start_time.timestamp()

    # Scavenge Maths
    def scavenge(self, state, troops):
        sca1 = []
        sca2 = []
        sca3 = []
        sca4 = []
        if state == 3:
            for element in troops:
                sca1.append(str(math.floor((5 / 8) * element)))
                sca2.append(str(math.floor((2 / 8) * element)))
                sca3.append(str(math.floor((1 / 8) * element)))
        if state == 4:
            for element in troops:
                sca1.append(str(math.floor(0.5765 * element)))
                sca2.append(str(math.floor(0.23 * element)))
                sca3.append(str(math.floor(0.1155 * element)))
                sca4.append(str(math.floor(0.077 * element)))

        return sca1, sca2, sca3, sca4

    # Silence Method
    async def silencer(self, coro):
        try:
            await coro
        except discord.Forbidden:
            pass


# Main Class
load = Load()
