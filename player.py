import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton, ParseMode

from actions import ACTIONS


def make_keyboard_markup(table):
    if table is not None:
        return ReplyKeyboardMarkup([[KeyboardButton(text) for _, text in row] for row in table], True)


class Player(object):

    def __init__(self, user_id, chat_id):
        self._user_id = user_id
        self._chat_id = chat_id
        self._location_id = "001"
        self._suggested_actions = None

    def set_actions(self, keyboard):
        self._suggested_actions = dict()
        for row in keyboard:
            for action, button_text in row:
                self._suggested_actions[button_text] = action

    def do_action(self, text, bot, gamedata):
        if text not in self._suggested_actions:
            logging.info("INVALID_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
            return
        if type(self._suggested_actions[text]) in {str, unicode}:
            action, args = self._suggested_actions[text], tuple()
        else:
            action, args = self._suggested_actions[text]._name, self._suggested_actions[text]._args
        if action not in ACTIONS:
            raise Exception("UNIMPLEMENTED_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
        ACTIONS[action](self, bot, gamedata, *args)
        return
        if len(parts) == 1:
            ACTIONS[action](self, bot, gamedata)
        else:
            ACTIONS[action](self, bot, gamedata, *args)

    def send_message(self, bot, text, keyboard=None):
        bot.send_message(self._chat_id, text,
                         reply_markup=make_keyboard_markup(keyboard),
                         parse_mode=ParseMode.HTML)
        if keyboard is not None:
            self.set_actions(keyboard)
