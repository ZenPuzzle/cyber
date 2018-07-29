#!/usr/bin/env python
from __future__ import print_function
try:
    import configparser
except:
    import ConfigParser as configparser

import psycopg2

from db import FIELDS

cfg = configparser.RawConfigParser()
cfg.read("config.ini")
kwargs = {
    "host": cfg.get("player_db", "host"),
    "dbname": cfg.get("player_db", "dbname"),
    "user": cfg.get("player_db", "user"),
    "password": cfg.get("player_db", "password")
}
with psycopg2.connect(**kwargs) as conn:
    with conn.cursor() as curs:
        curs.execute("SELECT * FROM Players")
        for row in curs.fetchall():
            print(*row)

#        command = "ALTER TABLE Players ADD LORE INTEGER, ADD RAW_LORE INTEGER, ADD LORE_LAST_UPDATE INTEGER"
#        print(command)
#        curs.execute(command)
        command = "UPDATE Players SET LORE = 1024, RAW_LORE = 0, LORE_LAST_UPDATE = null"
        print(command)
        curs.execute(command)

        curs.execute("SELECT * FROM Players")
        for row in curs.fetchall():
            print(*row)
