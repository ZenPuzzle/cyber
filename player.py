import logging
import time
import threading
from heapq import heappush

from telegram import ReplyKeyboardMarkup, KeyboardButton, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton

from actions import ACTIONS, Act


TICK_DURATION = 0.5

def make_keyboard_markup(table):
    if table is not None:
        return ReplyKeyboardMarkup([[KeyboardButton(text) for _, text in row] for row in table], True)


def make_inline_keyboard_markup(table):
    if table is not None:
        return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=text) for _, text in row] for row in table])


class Player(object):

    def __init__(self, user_id, chat_id):
        self._user_id = user_id
        self._chat_id = chat_id
        self._location_id = "001"
        self._suggested_actions = None
        self._delayed_action = None
        self._lock = threading.Lock()
        self._prev_message_id = None

    def set_actions(self, keyboard):
        self._suggested_actions = dict()
        for row in keyboard:
            for action, button_text in row:
                assert type(button_text) == unicode
                self._suggested_actions[button_text] = action

    def set_delayed_action(self, bot, ticks, action):
        self._delayed_action = action
        self._fullfill_time = time.time() + ticks * TICK_DURATION
        with bot.delayed_action_lock:
            heappush(bot.delayed_actions, (self._fullfill_time, 1, self._user_id))

    def do_action(self, action, bot, gamedata):
        if action._name not in ACTIONS:
            raise Exception("UNIMPLEMENTED_ACTION\t{}".format(action._name))
        logging.info("PLAYER:{}\tACTION: {}\tSUGGESTED_ACTIONS:{}".format(
            self._user_id, action._name,
            u" ".join(list(self._suggested_actions.iterkeys())).encode("utf8")))
        ACTIONS[action._name](self, bot, gamedata, *action._args)

    def handle_text_update(self, text, bot, gamedata):
        if text not in self._suggested_actions:
            logging.info(u"{} not in suggested actions".format(text).encode("utf8"))
            return
        if type(self._suggested_actions[text]) in {str, unicode}:
            action = Act(self._suggested_actions[text])
        else:
            action = self._suggested_actions[text]
        self.do_action(action, bot, gamedata)

    def send_message(self, bot, text, keyboard=None):
        self._prev_message_id = bot.send_message(self._chat_id, text,
                         reply_markup=make_keyboard_markup(keyboard),
                         parse_mode=ParseMode.HTML).message_id
        if keyboard is not None:
            self.set_actions(keyboard)
