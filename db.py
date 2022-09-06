import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

dbhost = os.getenv("DATABASE_HOST")
dbuser = os.getenv("DATABASE_USER")
dbpass = os.getenv("DATABASE_PASS")
dbname = os.getenv("DATABASE_NAME")

characters = {}

try:
    cnx = mysql.connector.connect(host=dbhost,
                                  database=dbname,
                                  user=dbuser,
                                  password=dbpass)
    if cnx.is_connected():
        dbinfo = cnx.get_server_info()
        print(f"Connected to server: {dbinfo}")

    cursor = cnx.cursor()
    sql = "select discord_id, character_url from characters"
    cursor.execute(sql)

    for (discord_id, url) in cursor:
        mychars = characters.setdefault(discord_id, set())
        mychars.add(url)


except Error as e:
    print("Error connecting to db", e)
finally:
    if cnx.is_connected():
        cnx.close()
        print("closed connection to db")

for character, url_set in characters.items():
    for url in url_set:
        print(f"Char: {character} - URL: {url}")
