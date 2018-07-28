#!/usr/bin/env python
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
        primary = " ".join(FIELDS[0])
        other = ", ".join([key + " " + value_type for key, value_type in FIELDS[1:]])
        assert other
        command = "CREATE TABLE Players({} PRIMARY KEY, {})".format(primary, other)
        print command
        curs.execute(command)
