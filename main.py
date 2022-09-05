import discord
import os
import requests
import json
import feedparser

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents = intents)

#@client.command()
#async def embed(ctx):
#  embed=discord.Embed(title="Testing", url="http://hoshisabi.com", description="This is a test")
#  await ctx.send(embed=embed)

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  if message.content.startswith('$inspire'):
    quote = get_quote()
    print(message)
    await message.channel.send(quote)

  if message.content.startswith('$rss'):
    rss = get_rss()
    print(rss)
    await message.channel.send(rss)


def get_quote():
  response = requests.get("https://zenquotes.io/api/random")
  json_data = json.loads(response.text)
  quote = json_data[0]['q'] + " -" + json_data[0]['a']
  return(quote)

def get_rss():
  rss = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
  #list = [(x.title,x.link) for x in rss.entries]
  list = [f"{x.title}: {x.link}" for x in rss.entries]
  print(list)
  return list

client.run(os.getenv('TOKEN'))
