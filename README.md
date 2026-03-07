# P4ND0-bot

A bot for the PandoDnD server

More information here: http://hoshisabi.com

If you need to access the sparkedhost site, the url is (billing and
info): https://billing.sparkedhost.com/clientarea.php

To directly access the panel, the url is: https://control.sparkedhost.us/server/21d23a9f

## Troubleshooting

### Missing Slash Commands

If you recently authorized or updated the bot and the `/` commands are not appearing in your client:

1. Discord heavily caches application commands locally to save bandwidth. Press `Ctrl+R` while Discord is focused to
   hard refresh the client.
2. If refreshing does not work, ensure the bot was invited to the server with the `applications.commands` scope checked
   in addition to the standard `bot` scope in the Developer Portal's OAuth2 URL generator.
