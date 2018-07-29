import logging
import json
import random
import time

from actions import ACTIONS
from constants import *


class Player(object):

    def __init__(self, user_id, chat_id, location_id="001", suggested_actions={},
                 lore=0, raw_lore=0, lore_last_update=None, research_percent={},
                 running_soft=set(), known_soft=set(), compiling_soft=[]):
        self._user_id = user_id
        self._chat_id = chat_id
        self._suggested_actions = suggested_actions
        self._lore = lore
        self._raw_lore = raw_lore
        self._lore_last_update = lore_last_update
        self._used_ram = 0
        self._used_cpu = 0
        self._research_percent = research_percent
        self.set_location(location_id)
        self._known_soft = known_soft
        self._running_soft = running_soft
        self._compiling_soft = compiling_soft

    def set_actions(self, keyboard):
        self._suggested_actions = dict()
        for row in keyboard:
            for action, button_text in row:
                self._suggested_actions[button_text] = action

    def set_location(self, loc_id):
        self._location_id = loc_id
        if loc_id not in self._research_percent:
            self._research_percent[loc_id] = 0

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

    def get_cpu(self):
        return int(self._lore ** 0.5)

    def get_used_cpu(self, gamedata):
        used = 0
        for program in self._running_soft:
            used += gamedata._programs[program]._cpu_usage
        if self._compiling_soft:
            program, cpu, start_time, last_check = self._compiling_soft
            used += cpu
        return used

    def get_ram(self):
        return self._lore / 10

    def get_used_ram(self, gamedata):
        used = 0
        for program in self._running_soft:
            used += gamedata._programs[program]._ram_usage
        return used

    def get_name(self):
        return u"id_{}".format(self._user_id)

    def compile_program(self, entity_id, gamedata):
        ts = time.time()
        free_cpu = self.get_cpu() - self.get_used_cpu(gamedata)
        self._compiling_soft = [entity_id, free_cpu / 2, ts, ts]

    def update_lore(self, gamedata):
        ts = time.time()
        if self._raw_lore > 0:
            time_since_update = int(ts - self._lore_last_update)
            processed_lore = int(min(time_since_update / 60.0 * self.get_cpu(), self._raw_lore))
            self._raw_lore -= processed_lore
            self._lore += processed_lore
        if self._compiling_soft:
            program, cpu, start_time, last_check = self._compiling_soft
            compile_time = gamedata._programs[program]._compile_time
            finish_ts = start_time + compile_time / cpu * TICK_DURATION
            if ts >= finish_ts:
                self._running_soft.add(program)
                self._compiling_soft = []

#            compile_check_period = 12 * TICK_DURATION
#
#            new_last_check = last_check + int((min(ts, finish_ts) - last_check) / compile_check_period) * compile_check_period
#            if new_last_check - last_check >= compile_check_period:
#                check_count = (new_last_check - last_check) / compile_check_period
#                if random.random() > 0.5 ** check_count:
#                    self._compiling_soft = None
#                else:
#                    self._compiling_soft[3] = new_last_check
#            if self._compiling_soft is not None:
#                if finish_ts <= ts:
#                    self._running_soft.append(program)
#                    self._compiling_soft = None


    @staticmethod
    def from_row(row):
        user_id, chat_id, location_id = row[:3]
        suggested_actions = json.loads(row[3])
        lore, raw_lore, lore_last_update = row[4:7]
        research_percent = json.loads(row[7])
        running_soft = set(json.loads(row[8]))
        known_soft = set(json.loads(row[9]))
        compiling_soft = json.loads(row[10])
        return Player(user_id, chat_id, location_id, suggested_actions, lore,
                      raw_lore, lore_last_update, research_percent,
                      running_soft, known_soft, compiling_soft)

    def to_row(self):
        serialized = json.dumps(self._suggested_actions)
        assert len(serialized) < SUGGESTED_ACTIONS_MAX_LEN
        research_percent = json.dumps(self._research_percent)
        assert len(research_percent) < SUGGESTED_ACTIONS_MAX_LEN
        return [
            self._user_id,
            self._chat_id,
            self._location_id,
            serialized,
            self._lore,
            self._raw_lore,
            self._lore_last_update,
            research_percent,
            json.dumps(list(self._running_soft)),
            json.dumps(list(self._known_soft)),
            json.dumps(self._compiling_soft)
        ]


def fetch_player(user_id, db):
    with db.connect() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT * FROM Players WHERE USER_ID = %s", (user_id,))
            rows = curs.fetchall()
            assert len(rows) <= 1, "duplicate user_id's in database: {}".format(user_id)
            if rows:
                return Player.from_row(rows[0])
