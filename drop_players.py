#!/usr/bin/env python
try:
    import configparser
except:
    import ConfigParser as configparser
import time

import psycopg2

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
        command = "DROP TABLE Players"
        print "will execute in 5 seconds:"
        print command
        time.sleep(5)
        curs.execute(command)
