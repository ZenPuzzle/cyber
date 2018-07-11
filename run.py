#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
import argparse
try:
    import configparser
except:
    import ConfigParser as configparser
import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

CONTINUE = "continue"
GO_N = u"⬆️"
GO_NE = u"↗️"
GO_E = u"▶️"
GO_SE = u"↘️"
GO_S = u"⬇️"
GO_SW = u"↙️"
GO_W = u"◀️"
GO_NW = u"↖️"
LOOK_AROUND = "look around"

class Location(object):

    def __init__(self, x = 0, y = 0, z = 0):
        self._x = x
        self._y = y
        self._z = z

    def __str__(self):
        return "({}, {}, {})".format(self._x, self._y, self._z)


def make_keyboard_markup(table):
    return ReplyKeyboardMarkup([[KeyboardButton(action) for action in row] for row in table], True)


def show_map(player, bot):
    text = "your location is: {}".format(player._loc)
    keyboard = [
        [GO_NW, GO_N, GO_NE],
        [GO_W, LOOK_AROUND, GO_E],
        [GO_SW, GO_S, GO_SE]
    ]
    bot.send_message(player._chat_id, text, reply_markup=make_keyboard_markup(keyboard))
    player.set_actions(keyboard)


class Player(object):

    def __init__(self, user_id, chat_id):
        self._user_id = user_id
        self._chat_id = chat_id
        self._loc = Location()
        self._suggested_actions = {CONTINUE}

    def set_actions(self, keyboard):
        self._suggested_actions = set()
        for row in keyboard:
            for action in row:
                self._suggested_actions.add(action)

    def do_action(self, text, bot):
        if text not in self._suggested_actions:
            logging.info("INVALID_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
            return
        if text == CONTINUE:
            show_map(self, bot)
        elif text == GO_N:
            self._loc._y += 1
            show_map(self, bot)
        elif text == GO_NE:
            self._loc._y += 1
            self._loc._x += 1
            show_map(self, bot)
        elif text == GO_E:
            self._loc._x += 1
            show_map(self, bot)
        elif text == GO_SE:
            self._loc._y -= 1
            self._loc._x += 1
            show_map(self, bot)
        elif text == GO_S:
            self._loc._y -= 1
            show_map(self, bot)
        elif text == GO_SW:
            self._loc._y -= 1
            self._loc._x -= 1
            show_map(self, bot)
        elif text == GO_W:
            self._loc._x -= 1
            show_map(self, bot)
        elif text == GO_NW:
            self._loc._y += 1
            self._loc._x -= 1
            show_map(self, bot)
        elif text == LOOK_AROUND:
            show_map(self, bot)
        else:
            raise Exception("UNIMPLEMENTED_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))


class StartCommandHandlerCallback(object):

    def __init__(self, players):
        self._players = players

    def __call__(self, bot, update):
        user_id = update.message.from_user.id
        if user_id in self._players:
            return
        logging.info("NEW_USER\t{}".format(user_id))
        self._players[user_id] = Player(user_id, update.message.chat_id)
        text = "User {} is welcome in chat {}".format(user_id, update.message.chat_id)
        bot.send_message(update.message.chat_id, text=text, reply_markup=make_keyboard_markup([[CONTINUE]]))


class TextHandlerCallback(object):

    def __init__(self, players):
        self._players = players

    def __call__(self, bot, update):
        chat_id = update.message.chat_id
        text = update.message.text
        player = self._players.get(update.message.from_user.id)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID")
        player.do_action(text, bot)


def handle_unknown(bot, update):
    bot.send_message(update.message.chat_id, text="unknown command")


def run_main_loop(token):
    updater = Updater(token=token)
    dispatcher = updater.dispatcher

    players = dict()

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        MessageHandler(Filters.text, TextHandlerCallback(players)),
        MessageHandler(Filters.all, handle_unknown)
    ]

    for handler in handlers:
        dispatcher.add_handler(handler)

    try:
        updater.start_polling()
    except Exception as e:
        logging.error("UPDATER_EXCEPTION: {}".format(e.message))
        updater.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = configparser.RawConfigParser()
    cfg.read(args.cfg)

    run_main_loop(cfg.get("auth", "token"))


if __name__ == "__main__":
    main()
