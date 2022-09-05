import feedparser
from datetime import datetime


def to_discordtimestamp(str):
    x = int(datetime.fromisoformat(str).timestamp())
    return x

print("2022-09-07T19:00:00-04:00")
print(to_discordtimestamp("2022-09-07T19:00:00-04:00"))
print("---")

rss = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
print(rss.entries[0])
print(rss.entries[0].gd_when)
strtime = to_discordtimestamp(rss.entries[0].gd_when['starttime'])
print(f"-{strtime}-")
#print(rss.entries[0].summary)

rsslist = [f"* [{x.title}]({x.link}) <t:{to_discordtimestamp(x.gd_when['starttime'])}>" for x in rss.entries]
rssoutput = "\n\t".join(rsslist)
reply = f"The following games are coming up:\n\n\t{rssoutput}\n"
print(reply)
