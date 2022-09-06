import feedparser
import markdownify
from datetime import datetime


def to_discordtimestamp(str):
    x = int(datetime.fromisoformat(str).timestamp())
    return x

print("2022-09-07T19:00:00-04:00")
print(to_discordtimestamp("2022-09-07T19:00:00-04:00"))
print("---")

rss_feed = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
print(rss_feed.entries[0])
print(rss_feed.entries[0].gd_when)
strtime = to_discordtimestamp(rss_feed.entries[0].gd_when['starttime'])
print(f"-{strtime}-")
#print(rss.entries[0].summary)

arg = True
desc_text = f"The following games are upcoming on this server, click on a link to schedule a seat.\n"
for x in rss_feed.entries:
    desc_text += f"  * [{x.title}]({x.link}) <t:{to_discordtimestamp(x.gd_when['starttime'])}>"
    if (arg):
        mdif = markdownify.markdownify(x.summary)
        lines = mdif.splitlines()
        desc_text += "\n>".join([line for line in lines if line.strip()])
    desc_text += "\n"

print(desc_text)
