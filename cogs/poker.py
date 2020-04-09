from discord.ext import commands
import asyncio
import discord
import random
import utils
import os


class Poker(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bj = {}
        self.vp = {}
        self.signs = ["h", "d", "c", "s"]
        self.numbers = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.full_set = [num + card for num in self.numbers for card in self.signs]
        self.converse = {"J": 11, "Q": 12, "K": 13, "A": 14}
        self.payout = {"Paar": 1.5, "Doppel-Paar": 2, "Drilling": 7.5,
                       "Straße": 20, "Flush": 40, "Full House": 60,
                       "Vierling": 100, "Straight Flush": 250, "Royal Flush": 500}

    async def victory_royale(self, guild_id, bj=False):
        cache = self.bj if bj else self.vp
        cache[guild_id] = False
        await asyncio.sleep(15)
        cache.pop(guild_id)

    def dealer(self, ctx, cash, bj=False):
        card_amount = 2 if bj else 5

        card_pack = []
        packs = 6 if bj else 1
        for _ in range(packs):
            card_pack.extend(self.full_set)

        hands = ['hand']

        if bj:
            hands.append('dealer')

        data = {}
        for key in hands:
            cards = []
            for _ in range(card_amount):
                card = random.choice(card_pack)
                cards.append(card)
                card_pack.remove(card)

            data[key] = cards

        data['cards'] = card_pack

        if bj:
            return data['hand'], data['dealer'], data['cards']

        else:
            stamp = ctx.message.created_at.timestamp()
            extra = {'author': ctx.author, 'bet': cash, 'time': stamp}
            data.update(extra)
            self.vp[ctx.guild.id] = data
            return data['hand'], stamp

    async def player_wins(self, ctx, data, bj=False):
        extra = data['bet'] * 1.5 if bj else data['bet']
        price = int(data['bet'] + extra)

        greet = "Blackjack" if bj else "Glückwunsch"
        base = f"{greet}, du gewinnst {utils.pcv(price)} Eisen!"
        embed = self.present_cards(data, base)
        embed.colour = discord.Color.green()

        await data['msg'].edit(embed=embed)
        await self.bot.update_iron(ctx.author.id, price)
        await self.victory_royale(ctx.guild.id, True)

    async def dealer_wins(self, ctx, data, tie=False, bj=False):
        if tie:
            base = "Unentschieden, du erhältst deinen Einsatz zurück"
            await self.bot.update_iron(ctx.author.id, data['bet'])

        else:
            word = "Blackjack" if bj else "RIP"
            base = f"{word}, du hast deinen Einsatz verloren"

        embed = self.present_cards(data, base)
        embed.colour = discord.Color.red()

        await data['msg'].edit(embed=embed)
        await self.victory_royale(ctx.guild.id, True)

    def present_cards(self, data, msg, player=False):
        dealer_hand = data['dealer'][:1] + ["X"] if player else data['dealer']
        hand = f"`{'`**|**`'.join(data['hand'])}` **[{data['result']}]**"
        dealer = f"`{'`**|**`'.join(dealer_hand)}` **[{data['score']}]**"

        msg_obj = data.get('msg')
        if msg_obj is None:
            embed = discord.Embed(description=f"**{msg}**", color=0xf497b8)
            embed.add_field(name="Deine Hand:", value=hand)
            embed.add_field(name="Dealer Hand:", value=dealer)
            embed.set_footer(text="15s Cooldown nach Abschluss der Runde")

        else:
            embed = msg_obj.embeds[0]
            embed.set_field_at(0, name="Deine Hand:", value=hand)
            embed.set_field_at(1, name="Dealer Hand:", value=dealer)
            embed.description = f"**{msg}**"

        return embed

    def blackjack(self, cards):
        card_signs = [c[:-1] for c in cards]
        values = {"J": 10, "Q": 10, "K": 10, "A": 11}
        count = 0

        for card in card_signs:
            spec = values.get(card)
            num = spec or int(card)
            count += num

        last = card_signs.count("A")
        for index in range(last + 1):
            if count <= 21:
                return count
            elif index != last:
                count -= 10

        return False

    def check_result(self, cards):
        card_numbers = [c[:-1] for c in cards]
        card_signs = [c[-1] for c in cards]

        street = []
        con = self.converse.copy()
        for _ in range(("A" in card_numbers) + 1):
            sequence = []
            for num in card_numbers:
                spec = con.get(num, num)
                sequence.append(int(spec))

            sequence.sort()
            begin, end = min(sequence), max(sequence)
            if sequence == list(range(begin, end + 1)):
                street = sequence
                break
            else:
                con["A"] = 1

        if len(set(card_signs)) == 1:
            if street and sum(street) == 60:
                return "Royal Flush"
            elif street:
                return "Straight Flush"
            else:
                return "Flush"

        elif street:
            return "Straße"

        else:

            hands = {'41': "Vierling", '32': "Full House",
                     '311': "Drilling", '221': "Doppel-Paar",
                     '2111': "Paar"}

            occurs = []
            for num in set(card_numbers):
                amount = card_numbers.count(num)
                occurs.append(str(amount))

            occurs.sort(reverse=True)
            return hands.get("".join(occurs))

    @utils.game_channel_only()
    @commands.command(name="vp", aliases=["videopoker"])
    async def vp_(self, ctx, bet: int):
        if not 100 <= bet <= 2000:
            raise utils.InvalidBet(100, 2000)

        data = self.vp.get(ctx.guild.id)
        if data is False:
            return

        elif data:
            name = data['author'].display_name
            msg = f"`{name}` ist noch in einer aktiven Runde."
            await ctx.send(msg)

        else:

            await self.bot.subtract_iron(ctx.author.id, bet)

            cards, stamp = self.dealer(ctx, bet)
            base = "Deine Karten: `{}`{}Ersetze diese mit **{}draw 1-5**"
            msg = base.format(" ".join(cards), os.linesep, ctx.prefix)
            begin = await ctx.send(msg)

            await asyncio.sleep(60)

            try:
                current = self.vp.get(ctx.guild.id)
                if stamp == current['time']:
                    await begin.edit(content="**Spielende:** Zeitüberschreitung(60s)")
                    self.vp.pop(ctx.guild.id)

            except TypeError:
                return

    @utils.game_channel_only()
    @commands.command(name="draw", aliases=["ziehen"])
    async def draw_(self, ctx, cards=None):
        data = self.vp.get(ctx.guild.id)
        if data is False:
            return

        elif not data:
            msg = "Du musst zuerst eine Runde mit {}vp <100-2000> beginnen."
            return await ctx.send(msg.format(ctx.prefix))

        elif data['author'] != ctx.author:
            name = data['author'].display_name
            return await ctx.send(f"{name} ist bereits in einer Runde.")

        if cards:
            try:
                if len(cards) > 5:
                    raise ValueError
                for num in set(cards):
                    num = int(num)
                    if not (0 < num < 6):
                        raise ValueError

                    new_card = random.choice(data['cards'])
                    data['hand'][num - 1] = new_card
                    data['cards'].remove(new_card)

            except ValueError:
                base = "**Fehlerhafte Eingabe**{}Beispiel: {}draw 134"
                msg = base.format(os.linesep, ctx.prefix)
                return await ctx.send(msg)

            card_rep = f"Deine neuen Karten: `{' '.join(data['hand'])}`"
        else:
            card_rep = f"Du behältst deine Karten: `{' '.join(data['hand'])}`"

        result = self.check_result(data['hand'])
        if result:
            pronoun = self.bot.msg['vpMessage'][result]
            amount = int(data['bet'] * self.payout[result])
            base = "{0}{1}Du hast {2} **{3}**: `{4} Eisen` gewonnen!{1}(15s Cooldown)"
            msg = base.format(card_rep, os.linesep, pronoun, result, amount)
            await self.bot.update_iron(ctx.author.id, amount)

        else:
            base = "{}{}**Du hast nichts und damit deinen Einsatz verloren** (15s Cooldown)"
            msg = base.format(card_rep, os.linesep)

        await ctx.send(msg)
        await self.victory_royale(ctx.guild.id)

    @utils.game_channel_only()
    @commands.command(name="bj", aliases=["blackjack"])
    async def bj_(self, ctx, bet: int):
        if not 100 <= bet <= 50000:
            raise utils.InvalidBet(100, 50000)

        game = self.bj.get(ctx.guild.id)
        if game is False:
            return

        elif game is True:
            msg = "Es läuft bereits eine Runde Blackjack"
            return await ctx.send(msg)

        else:
            self.bj[ctx.guild.id] = True

        await self.bot.subtract_iron(ctx.author.id, bet)
        hand, dealer, cache = self.dealer(ctx, bet, bj=True)

        result = self.blackjack(hand)
        game_data = {'hand': hand, 'result': result, 'dealer': dealer,
                     'score': self.blackjack(dealer[:1]), 'bet': bet}

        base = "Spiele mit h[hit], s[stand] oder d[double]"
        embed = self.present_cards(game_data, base, player=True)
        begin = await ctx.send(embed=embed)

        dealer_result = self.blackjack(dealer)
        game_data['msg'] = begin

        if result == 21:
            game_data['score'] = dealer_result
            await self.player_wins(ctx, game_data, bj=True)
            return

        moves = ["h", "s", "d"]

        def check(message):
            if message.author != ctx.author:
                return
            elif message.channel != ctx.channel:
                return
            else:
                return message.content.lower() in moves

        while True:

            if result == 21:
                move = "s"

            elif game_data['bet'] == bet:
                try:
                    reply = await self.bot.wait_for('message', check=check, timeout=60)
                    move = reply.content.lower()

                except asyncio.TimeoutError:
                    await begin.edit(content="**Spielende:** Zeitüberschreitung(60s)")
                    await self.victory_royale(ctx.guild.id, bj=True)
                    return

            else:
                move = "s"

            if move in ["h", "d"]:

                if len(moves) == 3:
                    moves.remove("d")

                if move == "d":
                    response = await self.bot.subtract_iron(ctx.author.id, bet, supress=True)
                    if response is None:
                        error = "\nDu hast nicht genügend Eisen..."
                        embed.description += error
                        await begin.edit(embed=embed)
                        continue

                    game_data['bet'] = bet * 2

                new_card = random.choice(cache)
                cache.remove(new_card)
                hand.append(new_card)
                result = self.blackjack(hand)
                game_data['result'] = result or "RIP"

                if result is False:
                    game_data['score'] = dealer_result
                    await self.dealer_wins(ctx, game_data)
                    return

                else:
                    base = "Spiele mit h[hit], s[stand]"
                    msg = self.present_cards(game_data, base, player=True)
                    await begin.edit(embed=msg)

            else:
                game_data['score'] = dealer_result
                while True:
                    if dealer_result == 21:
                        await self.dealer_wins(ctx, game_data, bj=len(dealer) == 2)
                        return

                    elif dealer_result is False:
                        await self.player_wins(ctx, game_data)
                        return

                    elif dealer_result >= 17:
                        if result > dealer_result:
                            await self.player_wins(ctx, game_data)
                        else:
                            tie = result == dealer_result
                            await self.dealer_wins(ctx, game_data, tie=tie)
                        return

                    new_card = random.choice(cache)
                    cache.remove(new_card)
                    dealer.append(new_card)
                    dealer_result = self.blackjack(dealer)
                    game_data['score'] = dealer_result or "RIP"

                    await asyncio.sleep(0.75)
                    msg = self.present_cards(game_data, base)
                    await begin.edit(embed=msg)


def setup(bot):
    bot.add_cog(Poker(bot))