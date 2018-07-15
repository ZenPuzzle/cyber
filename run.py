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

from map import Position, parse_gamedata, DIR2DIR_ID

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

CONTINUE = "continue"
DIR_ID2BUTTON = {
    "N": u"⬆️"
    "NE": u"↗️"
    "E": u"▶️"
    "SE": u"↘️"
    "S": u"⬇️"
    "SW": u"↙️"
    "W": u"◀️"
    "NW": u"↖️",
    "U": u"UP",
    "D": u"DOWN"
}
LOOK_AROUND = "look around"

START_LOCATION_ID = "001"

def make_keyboard_markup(table):
    return ReplyKeyboardMarkup([[KeyboardButton(action) for action in row] for row in table], True)


def make_direction_button(dir_id, transaction):
    rich_markup = ""
    if transaction._multiplier == 0:
        rich_markup = u"🚷"
    return DIR_ID2BUTTON[dir_id] + rich_markup


def parse_direction_button(full_button_text):
    direction = button[0]
    for dir_id, button in DIR_ID2BUTTON.iteritems():
        if button == full_button_text:
            return dir_id


def show_map(player, bot, geo):
    loc = geo[player._location_id]
    text = loc._descr
    keyboard = [
        list(map(lambda x: make_direction_button(x, loc.adjacent), "NW", "N", "NE")),
        make_direction_button("W", loc.adjacent), u"осмотреться", make_direction_button("E", loc.adjacent),
        list(map(lambda x: make_direction_button(x, loc.adjacent), "SW", "S", "SE"))
    ]
    bot.send_message(player._chat_id, text, reply_markup=make_keyboard_markup(keyboard))
    player.set_actions(keyboard)


class Player(object):

    def __init__(self, user_id, chat_id):
        self._user_id = user_id
        self._chat_id = chat_id
        self._location_id = START_LOCATION_ID
        self._suggested_actions = {CONTINUE}

    def set_actions(self, keyboard):
        self._suggested_actions = set()
        for row in keyboard:
            for action in row:
                self._suggested_actions.add(action)

    def do_action(self, text, bot, geo):
        if text not in self._suggested_actions:
            logging.info("INVALID_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
            return
        if text == CONTINUE:
            show_map(self, bot, geo)
        elif text in DIR_ID2BUTTON:
            transition = geo[self._location_id].adjacent[text]
            bot.send_message(self._chat_id, transition._descr)
            self._location_id = transition.to_id
            show_map(self, bot, geo)
        elif text == LOOK_AROUND:
            show_map(self, bot, geo)
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

    def __init__(self, players, geo):
        self._players = players
        self._geo = geo

    def __call__(self, bot, update):
        chat_id = update.message.chat_id
        text = update.message.text
        player = self._players.get(update.message.from_user.id)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID")
        player.do_action(text, bot, self._geo)


def handle_unknown(bot, update):
    bot.send_message(update.message.chat_id, text="unknown command")


def run_main_loop(token, game_map):
    updater = Updater(token=token)
    dispatcher = updater.dispatcher

    players = dict()

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        MessageHandler(Filters.text, TextHandlerCallback(players, game_map)),
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

    game_map = parse_gamedata(cfg.get("gamedata", "xml"))
    run_main_loop(cfg.get("auth", "token"), game_map)


if __name__ == "__main__":
    main()
