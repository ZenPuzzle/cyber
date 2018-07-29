import psycopg2
from telegram import ReplyKeyboardMarkup, KeyboardButton, ParseMode

from constants import *

class DB(object):

    def __init__(self, host, dbname, user, password):
        self._host = host
        self._dbname = dbname
        self._user = user
        self._password = password

    def connect(self):
        return psycopg2.connect(host=self._host, user=self._user,
                                dbname=self._dbname, password=self._password)

FIELDS = [
    ("USER_ID", "INTEGER"),
    ("CHAT_ID", "INTEGER"),
    ("LOCATION_ID", "VARCHAR({})".format(LOCATION_ID_MAX_LEN)),
    ("SUGGESTED_ACTIONS", "VARCHAR({})".format(SUGGESTED_ACTIONS_MAX_LEN)),
    ("LORE", "INTEGER"),
    ("RAW_LORE", "INTEGER"),
    ("LORE_LAST_UPDATE", "INTEGER"),
    ("RESEARCH_PERCENT", "VARCHAR({})".format(SUGGESTED_ACTIONS_MAX_LEN))
]


def add_player(player, conn):
    with conn.cursor() as curs:
        placeholders = ", ".join(["%s" for field, _ in FIELDS])
        curs.execute("INSERT INTO Players VALUES ({})".format(placeholders), player.to_row())


def update_player(player, conn):
    with conn.cursor() as curs:
        placeholders = ", ".join(["{} = %s".format(field) for field, _ in FIELDS[1:]])
        curs.execute("UPDATE Players SET {} WHERE USER_ID = %s".format(placeholders),
                     player.to_row()[1:] + [player._user_id])


def make_keyboard_markup(table):
    if table is not None:
        return ReplyKeyboardMarkup([[KeyboardButton(text) for _, text in row] for row in table], True)


def send_message(player, conn, bot, text, keyboard=None):
    chat_id = player._chat_id
    if keyboard is None:
        bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        return
    player.set_actions(keyboard)
    update_player(player, conn)
    bot.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                         reply_markup=make_keyboard_markup(keyboard))
