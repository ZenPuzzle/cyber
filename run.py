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

from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from map import load_gamedata, get_gamedata_status
from player import Player
import delayed_actions

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
        keyboard = [[("CONTINUE", u"Продолжить")]]
        self._players[user_id].send_message(bot, text, keyboard)

class ReloadCommandHandlerCallback(object):

    def __init__(self, players, gamedata, credentials, spreadsheet_id):
        self._players = players
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

        self._players.clear()
        self._gamedata.update(new_game_data)
        bot.send_message(update.message.chat_id,
                         text=u"Game data was updated.\n{}\nRestart game: /start".format(
                             get_gamedata_status(self._gamedata)))

class TextHandlerCallback(object):

    def __init__(self, players, gamedata):
        self._players = players
        self._gamedata = gamedata

    def __call__(self, bot, update):
        chat_id = update.message.chat_id
        text = update.message.text
        player = self._players.get(update.message.from_user.id)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID")
        player.handle_text_update(text, bot, self._gamedata)

class InlineKeyboardHandlerCallback(object):

    def __init__(self, players, gamedata):
        self._players = players
        self._gamedata = gamedata

    def __call__(self, bot, update):
        user_id = update.callback_query.from_user.id
        player = self._players.get(user_id)
        if player is None:
            raise Exception("UNEXPECTED_USER_ID: {}".format(user_id.encode("utf8")))
        player.handle_text_update(update.callback_query.data, bot, self._gamedata)


def run_main_loop(token, credentials, spreadsheet_id):
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

    players = dict()

    threading.Thread(target=delayed_actions.run_routine,
                     args=(updater.bot, players, gamedata)).start()

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        CommandHandler("reload", ReloadCommandHandlerCallback(players,
                        gamedata, credentials, spreadsheet_id)),
        MessageHandler(Filters.text, TextHandlerCallback(players, gamedata))
#        CallbackQueryHandler(InlineKeyboardHandlerCallback(players, gamedata))
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

    run_main_loop(cfg.get("auth", "token"), cfg.get("auth", "credentials"),
                  cfg.get("gamedata", "spreadsheet_id"))


if __name__ == "__main__":
    main()
