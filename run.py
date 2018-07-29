#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
import argparse
try:
    import configparser
except:
    import ConfigParser as configparser
import logging
import threading
import json

from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, Handler

from map import load_gamedata, get_gamedata_status
from player import Player, fetch_player
import delayed_actions
from db import DB, add_player, update_player, send_message


class StartCommandHandlerCallback(object):

    def __init__(self, players):
        self._players = players

    def __call__(self, bot, update):
        user_id = update.message.from_user.id
        player = fetch_player(user_id, self._players)
        if player is not None:
            return
        player = Player(user_id, update.message.chat_id)
        text = "User {} is welcome in chat {}".format(user_id, update.message.chat_id)
        keyboard = [[("CONTINUE", u"Продолжить")]]
        with self._players.connect() as conn:
            add_player(player, conn)
            send_message(player, conn, bot, text, keyboard)
        logging.info("NEW_USER\t{}".format(user_id))

class RestartCommandHandlerCallback(object):

    def __init__(self, players):
        self._players = players

    def __call__(self, bot, update):
        user_id = update.message.from_user.id
        player = fetch_player(user_id, self._players)
        if player is None:
            return
        player = Player(user_id, update.message.chat_id)
        text = "User {} is welcome in chat {}".format(user_id, update.message.chat_id)
        keyboard = [[("CONTINUE", u"Продолжить")]]
        with self._players.connect() as conn:
            update_player(player, conn)
            send_message(player, conn, bot, text, keyboard)
        logging.info("NEW_USER\t{}".format(user_id))

class ReloadCommandHandlerCallback(object):

    def __init__(self, gamedata, credentials, spreadsheet_id):
        self._gamedata = gamedata
        self._credentials = credentials
        self._spreadsheet_id = spreadsheet_id

    def __call__(self, bot, update):
        bot.send_message(update.message.chat_id, text="Refreshing game data...")
        bot.send_chat_action(update.message.chat_id, ChatAction.TYPING, timeout=15)
        try:
            new_game_data = load_gamedata(self._credentials, self._spreadsheet_id)
        except Exception as e:
            bot.send_message(update.message.chat_id,
                text="Failed to load gamedata. Details: {}".format(e))
            return

        self._gamedata.update(new_game_data)
        bot.send_message(update.message.chat_id,
                         text=u"Game data was updated.\n{}".format(
                             get_gamedata_status(self._gamedata)))

class TextHandlerCallback(object):

    def __init__(self, players, gamedata):
        self._players = players
        self._gamedata = gamedata

    def __call__(self, bot, update):
        user_id = update.message.from_user.id
        player = fetch_player(user_id, self._players)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID: {}".format(user_id))
        text = update.message.text
        player.handle_text_update(text, bot, self._gamedata, self._players)

class ViewItemCommandHandler(Handler):

    def __init__(self, players, gamedata):
        Handler.__init__(self, None)
        self._gamedata = gamedata
        self._players = players

    @staticmethod
    def get_item_id(update):
        return update.message.text[len(u"/view_"):]

    def check_update(self, update):
        if update.message is not None and update.message.text.startswith(u"/view_i_"):
            return self.get_item_id(update) in self._gamedata._items
        return False

    def handle_update(self, update, dispatcher):
        bot = dispatcher.bot
        user_id = update.message.from_user.id
        player = fetch_player(user_id, self._players)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID: {}".format(user_id))
        bot.send_message(player._chat_id, self._gamedata._items[self.get_item_id(update)].get_info())


def run_main_loop(token, credentials, spreadsheet_id, players):
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="load_log.tsv")
    gamedata = load_gamedata(credentials, spreadsheet_id)
    logging.info(get_gamedata_status(gamedata).encode("utf8"))

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="log.tsv")
    updater = Updater(token=token)
    updater.bot.delayed_action_lock = threading.Lock()
    updater.bot.delayed_actions = list()
    dispatcher = updater.dispatcher

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        CommandHandler("restart", RestartCommandHandlerCallback(players)),
        CommandHandler("reload",
                       ReloadCommandHandlerCallback(gamedata, credentials,
                                                    spreadsheet_id)
                       ),
        MessageHandler(Filters.text, TextHandlerCallback(players, gamedata)),
        ViewItemCommandHandler(players, gamedata)
    ]

    for handler in handlers:
        dispatcher.add_handler(handler)

    updater.start_polling()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = configparser.RawConfigParser()
    cfg.read(args.cfg)

    players = DB(cfg.get("player_db", "host"), cfg.get("player_db", "dbname"),
            cfg.get("player_db", "user"), cfg.get("player_db", "password"))
    run_main_loop(cfg.get("auth", "token"), cfg.get("auth", "credentials"),
                  cfg.get("gamedata", "spreadsheet_id"), players)


if __name__ == "__main__":
    main()
