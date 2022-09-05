import feedparser
import json


rss = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
print(rss.entries[0])
print(rss.entries[0].gd_when)
print(rss.entries[0].gd_when['starttime'])

rsslist = [f"{x.title} {x.gd_when['starttime']}: {x.link}" for x in rss.entries]
rssoutput = "\n\t".join(rsslist)
reply = f"The following games are coming up:\n\n\t{rssoutput}\n"
print(reply)
