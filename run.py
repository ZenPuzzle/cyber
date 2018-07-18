#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
import argparse
try:
    import configparser
except:
    import ConfigParser as configparser
import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton, ChatAction, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from map import Position, load_gamedata, DIR2DIR_ID


WELCOME_SCREEN_KEYBOARD = [
    [("CONTINUE", u"Продолжить")]
]

MAP_KEYBOARD = [
    [("GO_NW", u"↖️"), ("GO_N", u"⬆️"), ("GO_NE", u"↗️")],
    [("GO_W", u"◀️"), ("LOOKAROUND", u"Оглядеться"), ("GO_E", u"▶️")],
    [("GO_SW", u"↙️"), ("GO_S", u"⬇️"), ("GO_SE", u"↘️")]
]


def can_go(dir_id, adj, geo):
    return (dir_id in adj) and (adj[dir_id]._to_id in geo) and adj[dir_id]._multiplier > 0


def do_go(player, bot, geo, dir_id):
    loc = geo[player._location_id]
    transition = loc._adjacent.get(dir_id)
    bot.send_message(player._chat_id, transition._descr)
    player.set_actions([])
    if can_go(dir_id, loc._adjacent, geo):
        player._location_id = transition._to_id
    show_map(player, bot, geo)


def do_look_around(player, bot, geo):
    show_map(player, bot, geo)


def do_continue(player, bot, geo):
    show_map(player, bot, geo)


ACTIONS = {
    "GO": do_go,
    "LOOKAROUND": do_look_around,
    "CONTINUE": do_continue
}

START_LOCATION_ID = "001"


def make_keyboard_markup(table):
    return ReplyKeyboardMarkup([[KeyboardButton(text) for _, text in row] for row in table], True)


def make_pretty_button(action, button, adj, geo):
    if not action.startswith("GO"):
        return button
    dir_id = action.split("_")[1]
    return adj[dir_id]._arrow + adj[dir_id]._extra_button_markup


def show_map(player, bot, geo):
    loc = geo[player._location_id]
    text = loc._descr
    keyboard = [
        [(action, make_pretty_button(action, button, loc._adjacent, geo)) for action, button in row]
        for row in MAP_KEYBOARD
    ]
    bot.send_message(player._chat_id, player._location_id + u" " + text,
                     parse_mode=ParseMode.HTML, reply_markup=make_keyboard_markup(keyboard))
    player.set_actions(keyboard)


class Player(object):

    def __init__(self, user_id, chat_id):
        self._user_id = user_id
        self._chat_id = chat_id
        self._location_id = START_LOCATION_ID
        self._suggested_actions = None

    def set_actions(self, keyboard):
        self._suggested_actions = dict()
        for row in keyboard:
            for action, button_text in row:
                self._suggested_actions[button_text] = action

    def do_action(self, text, bot, geo):
        if text not in self._suggested_actions:
            logging.info("INVALID_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
            return
        parts = self._suggested_actions[text].split("_")
        action, args = parts[0], parts[1:] if len(parts) > 1 else None
        if action not in ACTIONS:
            raise Exception("UNIMPLEMENTED_ACTION\t{}\t{}".format(self._user_id, text.encode("utf8")))
        if len(parts) == 1:
            ACTIONS[action](self, bot, geo)
        else:
            ACTIONS[action](self, bot, geo, *args)


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
        bot.send_message(update.message.chat_id, text=text,
                         reply_markup=make_keyboard_markup(WELCOME_SCREEN_KEYBOARD))
        self._players[user_id].set_actions(WELCOME_SCREEN_KEYBOARD)


class ReloadCommandHandlerCallback(object):

    def __init__(self, players, game_map, credentials, spreadsheet_id):
        self._players = players
        self._game_map = game_map
        self._credentials = credentials
        self._spreadsheet_id = spreadsheet_id

    def __call__(self, bot, update):
        bot.send_message(update.message.chat_id, text="Refreshing game data...")
        bot.send_chat_action(update.message.chat_id, ChatAction.TYPING, timeout=15)
        try:
            new_game_map = load_gamedata(self._credentials, self._spreadsheet_id)
        except Exception as e:
            bot.send_message(update.message.chat_id,
                text="Failed to load gamedata. Details:\n{}".format(e.message))
            return

        self._players.clear()
        self._game_map.clear()
        self._game_map.update(new_game_map)
        bot.send_message(update.message.chat_id,
                         text="Success! Restart game: /start")


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


def run_main_loop(token, credentials, spreadsheet_id):
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="load_log.tsv")
    game_map = load_gamedata(credentials, spreadsheet_id)

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="log.tsv")
    updater = Updater(token=token)
    dispatcher = updater.dispatcher

    players = dict()

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        CommandHandler("reload", ReloadCommandHandlerCallback(players,
                        game_map, credentials, spreadsheet_id)),
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

    run_main_loop(cfg.get("auth", "token"), cfg.get("auth", "credentials"),
                  cfg.get("gamedata", "spreadsheet_id"))


if __name__ == "__main__":
    main()
