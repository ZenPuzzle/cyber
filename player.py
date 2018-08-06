import logging
import json
import random
import time

from actions import ACTIONS, COMMANDS
from constants import *

class Container(object):

    def __init__(self, items):
        self._max_weight = 15
        self._items = items

    def insert_item(self, item_id, count):
        for index, pair in enumerate(self._items):
            cur_item_id, cur_count = pair
            if item_id == cur_item_id:
                self._items[index][1] += count
                return
        self._items.append([item_id, count])

    def remove_item(self, item_id, count):
        for index, pair in enumerate(self._items):
            cur_item_id, cur_count = pair
            if item_id == cur_item_id:
                if self._items[index][1] < count:
                    raise Exception("trying to remove more than have")
                self._items[index][1] -= count
                if self._items[index][1] == 0:
                    del self._items[index]
                return
        raise Exception("trying to remove unexisting item {}".format(item_id))

    def get_count(self, item_id):
        for index, pair in enumerate(self._items):
            cur_item_id, cur_count = pair
            if item_id == cur_item_id:
                return self._items[index][1]
        return 0

    def get_weight(self, gamedata):
        result = 0
        for item_id, count in self._items:
            result += gamedata._items[item_id]._weight * count
        return result

    def to_dict(self):
        return {"items": self._items}

    @staticmethod
    def from_dict(d):
        return Container(d["items"])

class Avatar(object):

    def __init__(self, backpack=Container([])):
        self._backpack = backpack

    def to_dict(self):
        return {"backpack": self._backpack.to_dict()}

    @staticmethod
    def from_dict(d):
        return Avatar(Container.from_dict(d["backpack"]))


class Player(object):

    def __init__(self, user_id, chat_id, location_id="001", suggested_actions={},
                 lore=1024, raw_lore=0, lore_last_update=None, research_percent={},
                 running_soft=set(), known_soft=set(), compiling_soft=[],
                 installed_soft=set(), avatar=Avatar(), known_entities=set()):
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
        self._installed_soft = installed_soft
        self._avatar = avatar
        self._known_entities = known_entities

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
        if name not in ACTIONS and name not in COMMANDS:
            raise Exception("UNIMPLEMENTED_ACTION\t{}".format(name))
        assert name not in ACTIONS or name not in COMMANDS
        logging.info("PLAYER: {}\tACTION: {}\tSUGGESTED_ACTIONS:{}".format(
            self._user_id, name,
            json.dumps(self._suggested_actions,
                       ensure_ascii=False).encode("utf8"))
        )
        if name in ACTIONS:
            ACTIONS[name](self, bot, gamedata, pdb, *args)
        elif name in COMMANDS:
            COMMANDS[name](self, bot, gamedata, pdb, *args)

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

    def get_lore_for_new_entity(self, entity_id, gamedata):
        if entity_id in self._known_entities:
            return 0
        d = 2.0 * (300 * len(gamedata._map) - 10 * len(gamedata._items)) / len(gamedata._items) / (len(gamedata._items) + 1)
        gained = int(10 + len(self._known_entities) * d)
        self._known_entities.add(entity_id)
        self._raw_lore += gained
        return gained

    def compile_program(self, entity_id, gamedata):
        ts = time.time()
        free_cpu = self.get_cpu() - self.get_used_cpu(gamedata)
        if free_cpu < 1:
            return False
        self._compiling_soft = [entity_id, free_cpu / 2, ts, ts]
        return True

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
                self._installed_soft.add(program)
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
        installed_soft = set(json.loads(row[11]))
        avatar = Avatar.from_dict(json.loads(row[12])) if row[12] is not None else None
        known_entities = set(json.loads(row[13]))
        return Player(user_id, chat_id, location_id, suggested_actions, lore,
                      raw_lore, lore_last_update, research_percent,
                      running_soft, known_soft, compiling_soft, installed_soft,
                      avatar, known_entities)

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
            json.dumps(self._compiling_soft),
            json.dumps(list(self._installed_soft)),
            json.dumps(self._avatar.to_dict()) if self._avatar is not None else None,
            json.dumps(list(self._known_entities))
        ]


def fetch_player(user_id, db):
    with db.connect() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT * FROM Players WHERE USER_ID = %s", (user_id,))
            rows = curs.fetchall()
            assert len(rows) <= 1, "duplicate user_id's in database: {}".format(user_id)
            if rows:
                return Player.from_row(rows[0])
