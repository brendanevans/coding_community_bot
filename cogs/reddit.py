from discord.ext import commands, tasks
from discord import PermissionOverwrite, client
from random import sample

from traceback import print_tb

import json
import praw
from itertools import chain

class AutoRedditBase:
    def __init__(self, config_path):
        self.config_path = config_path
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2, separators=(',', ': '))

class AutoRedditChannel(AutoRedditBase):
    
    def __init__(self, channel, config_path):
        super().__init__(config_path)
        self.channel = channel
        # Test to see if the channel is in the config, initialize it to an empty list if not
        try:
            self.config[str(self.channel.guild.id)]['reddit_config'][str(channel.id)]
        except KeyError:
            self.config[str(self.channel.guild.id)]['reddit_config'][str(channel.id)] = []
        finally:
            self.config = self.config[str(self.channel.guild.id)]['reddit_config'][str(channel.id)]


    def __iadd__(self, new_subreddit):
        self.subreddits.append(new_subreddit)
        self.save_config()
        return self

    def __isub__(self, subreddit_to_remove):
        self.subreddits.remove(subreddit_to_remove)
        self.save_config()
        return self

class AutoRedditGuild(AutoRedditBase):

    def __init__(self, guild, config_path):
        super().__init__(config_path)
        self.guild = guild
        self.channels = self.config[str(self.guild.id)]['reddit_config']

    def __call__(self):
        state = self.guild.id in self.config['reddit_enabled']
        guild_id = self.guild.id
        if state is True:
            self.config['reddit_enabled'].remove(guild_id)
        else:
            self.config['reddit_enabled'].append(guild_id)
        self.save_config()

    def __iadd__(self, new_channel):
        self.channels[str(new_channel.id)] = []
        self.save_config()
        return self

    def __isub__(self, channel_to_remove):
        self.channels.pop(str(channel_to_remove.id))
        self.save_config()
        return self



class Reddit(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config_path = 'assets/config.json'
        self.config_full = json.load(open(self.config_path, 'r'))
        self.reddit = self.reddit_bot()
        self.timeframes = ['all', 'year', 'month']

        self.get_reddit.start()

    def reddit_bot(self):
        reddit_config = self.config_full['reddit_config']
        reddit = praw.Reddit(
            client_id=reddit_config['client_id'],
            client_secret=reddit_config['client_secret'],
            user_agent='Coding Community Bot/1.0',
            username=reddit_config['username'],
            password=reddit_config['password']
        )
        return reddit

    async def topinxperiod(self, subreddit, period='year', return_quantity=3):
        try:
            if return_quantity > 7:
                return_quantity = 7

            # relevant documentation https://praw.readthedocs.io/en/latest/code_overview/models/subreddit.html
            content = [submission.url for submission in self.reddit.subreddit(
                subreddit).top(period, limit=return_quantity)]
            return content
        except Exception as e:
            print(str(e))

    async def readings_fetch(self, subreddits_list, period='year', mode='top'):
        top_links_in_period = []

        if mode == 'assorted':
            links_per_sub = 3
        else:
            links_per_sub = 5

        try:
            for subreddit in subreddits_list:
                top_links_in_period.extend(await self.topinxperiod(
                                                                    subreddit,
                                                                    period=period,
                                                                    return_quantity=links_per_sub
                                                                    )
                                        )
        except Exception as e:
            print(e)

        top_links_in_period = sample(top_links_in_period, 1)

        while len('\n'.join([str(x) for x in top_links_in_period])) > 2000:
            top_links_in_period.pop(-1)

        return '\n'.join([str(x) for x in top_links_in_period])

    @tasks.loop(hours=12)
    async def get_reddit(self):
        for guild_id in self.config_full["reddit_enabled"]:
            for channel_id in self.config_full[str(guild_id)]['reddit_config'].keys():
                channel_object = self.bot.get_channel(int(channel_id))
                try:
                    period = sample(self.timeframes, 1)[0]

                    # category is a list of randomly sampled subreddit names to be concatenated after r/
                    category = sample(self.config_full[str(guild_id)]['reddit_config'][channel_id], 1)
                    await channel_object.send(await self.readings_fetch(category, period=period, mode='assorted'))

                except Exception as e:
                    print(e)

    @get_reddit.before_loop
    async def before_get_reddit(self):
        await self.bot.wait_until_ready()

    @commands.command()
    async def get_reddit_test(self, ctx):
        for guild_id in self.config_full["reddit_enabled"]:
            for channel_id in self.config_full[str(guild_id)]['reddit_config'].keys():
                channel_object = self.bot.get_channel(int(channel_id))
                try:
                    period = sample(self.timeframes, 1)[0]

                    # category is a list of randomly sampled subreddit names to be concatenated after r/
                    category = sample(self.config_full[str(guild_id)]['reddit_config'][channel_id], 1)
                    await channel_object.send(await self.readings_fetch(category, period=period, mode='assorted'))

                except Exception as e:
                    print(e)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def reddit(self, ctx, state: bool):
        """Enable or disable the reddit system"""
        guild = ctx.guild

        if ctx.args == None:
            AutoRedditGuild(guild, self.config_path)()

        if ctx.args[0] == type(ctx.channel):
            if ctx.args[1][0] == '+':
                AutoRedditChannel(guild, ctx.channel, self.config_path) + ctx.args[1][1:]

            elif ctx.args[1][0] == '-':
                AutoRedditChannel(guild, ctx.channel, self.config_path) - ctx.args[1][1:]






def setup(bot):
    bot.add_cog(Reddit(bot))
