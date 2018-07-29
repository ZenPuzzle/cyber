import logging
import json
import time

from actions import ACTIONS
from constants import *


class Player(object):

    def __init__(self, user_id, chat_id, location_id="001", suggested_actions={},
                 lore=0, raw_lore=0, lore_last_update=None):
        self._user_id = user_id
        self._chat_id = chat_id
        self._location_id = location_id
        self._suggested_actions = suggested_actions
        self._lore = lore
        self._raw_lore = raw_lore
        self._lore_last_update = lore_last_update
        self._used_ram = 0
        self._used_cpu = 0

    def set_actions(self, keyboard):
        self._suggested_actions = dict()
        for row in keyboard:
            for action, button_text in row:
                self._suggested_actions[button_text] = action

    def do_action(self, action, bot, gamedata, pdb):
        name = action[0]
        args = action[1:] if len(action) > 1 else tuple()
        if name not in ACTIONS:
            raise Exception("UNIMPLEMENTED_ACTION\t{}".format(name))
        logging.info("PLAYER: {}\tACTION: {}\tSUGGESTED_ACTIONS:{}".format(
            self._user_id, name,
            json.dumps(self._suggested_actions,
                       ensure_ascii=False).encode("utf8"))
        )
        ACTIONS[name](self, bot, gamedata, pdb, *args)

    def handle_text_update(self, text, bot, gamedata, pdb):
        if text not in self._suggested_actions:
            logging.info(u"{} not in suggested actions".format(text).encode("utf8"))
            return
        action = self._suggested_actions[text]
        if type(action) in {str, unicode}:
            action = (action,)
        self.do_action(action, bot, gamedata, pdb)

    @staticmethod
    def from_row(row):
        user_id, chat_id, location_id = row[:3]
        suggested_actions = json.loads(row[3])
        lore, raw_lore, lore_last_update = row[4:7]
        return Player(user_id, chat_id, location_id, suggested_actions, lore,
                      raw_lore, lore_last_update)

    def get_cpu(self):
        return int(self._lore ** 0.5)

    def get_ram(self):
        return self._lore / 10

    def get_name(self):
        return u"id_{}".format(self._user_id)

    def update_lore(self):
        if self._raw_lore > 0:
            time_since_update = int(time.time() - self._lore_last_update)
            processed_lore = min(time_since_update * self.get_cpu(), self._raw_lore)
            self._raw_lore -= processed_lore
            self._lore += processed_lore

    def to_row(self):
        serialized = json.dumps(self._suggested_actions)
        assert len(serialized) < SUGGESTED_ACTIONS_MAX_LEN
        self.update_lore()
        return [
            self._user_id,
            self._chat_id,
            self._location_id,
            serialized,
            self._lore,
            self._raw_lore,
            self._lore_last_update
        ]


def fetch_player(user_id, db):
    with db.connect() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT * FROM Players WHERE USER_ID = %s", (user_id,))
            rows = curs.fetchall()
            assert len(rows) <= 1, "duplicate user_id's in database: {}".format(user_id)
            if rows:
                return Player.from_row(rows[0])
