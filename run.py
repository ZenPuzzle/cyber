#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
import argparse
try:
    import configparser
except:
    import ConfigParser as configparser
import logging
import random

from telegram import ReplyKeyboardMarkup, KeyboardButton, ChatAction, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from map import load_gamedata, get_gamedata_status

class Act(object):

    def __init__(self, name, *args):
        self._name = name
        self._args = args


MAP_KEYBOARD = [
    [("SUPERMIND", u"🌐"), (Act("GO", "NW"), u"↖️"), (Act("GO", "N"), u"⬆️"), (Act("GO", "NE"), u"↗️")],
    [("LAB", u"🗺"), (Act("GO", "W"), u"◀️"), ("SHOWVENUES", u"🔄"), (Act("GO", "E"), u"▶️")],
    [("AVATAR", u"🤡"), (Act("GO", "SW"), u"↙️"), (Act("GO", "S"), u"⬇️"), (Act("GO", "SE"), u"↘️")]
]


def make_keyboard_markup(table):
    if table is not None:
        return ReplyKeyboardMarkup([[KeyboardButton(text) for _, text in row] for row in table], True)


def make_pretty_button(action, button, adj):
    if type(action) == str:
        return button
    dir_id = action._args[0]
    return adj[dir_id]._arrow + adj[dir_id]._extra_button_markup


def can_go(dir_id, adj, gamedata):
    return (dir_id in adj) and (adj[dir_id]._to_id in gamedata._map) and adj[dir_id]._multiplier > 0


def do_show_map(player, bot, gamedata):
    loc = gamedata._map[player._location_id]
    text = player._location_id + u" " + loc._descr
    keyboard = [
        [(action, make_pretty_button(action, button, loc._adjacent)) for action, button in row]
        for row in MAP_KEYBOARD
    ]
    player.send_message(bot, text, keyboard)


def get_show_venues_keyboard(player, gamedata):
    loc = gamedata._map[player._location_id]
    keyboard = [
        [("SUPERMIND", u"🌐"), ("LAB", u"🗺"), ("AVATAR", u"🤡"), ("SHOWMAP", u"🔄")]
    ]
    for venue_id in loc._venues:
        if venue_id in gamedata._venues:
            for option in gamedata._venues[venue_id]._options:
                keyboard.append([(Act(u"VENUEACTION", option[0], option[1]), option[0])])
    return keyboard


def do_show_venues(player, bot, gamedata):
    loc = gamedata._map[player._location_id]
    text = player._location_id + u" " + loc._descr
    keyboard = get_show_venues_keyboard(player, gamedata)
    player.send_message(bot, text, keyboard)


def choose_outcome(outcomes):
    p = random.random()
    for accu_prob, outcome in outcomes:
        if p < accu_prob:
            return outcome
    assert False, "bad probabilities"


def do_get_outcome(player, bot, gamedata, event_id, text_id, option_text, show_descr):
    descr, options = gamedata._texts[event_id][text_id]
    outcome = choose_outcome(options[option_text])
    message_parts = list()
    if show_descr:
        message_parts.append(descr)
    if outcome._message:
        message_parts.append(outcome._message)
    if outcome._outcome_id:
        message_parts.append(outcome._outcome_id)
    message = u"\n...\n".join(message_parts).encode("utf8")
    keyboard = get_show_venues_keyboard(player, gamedata)
    player.send_message(bot, message, keyboard)


def do_venue_action(player, bot, gamedata, venue_option, venue_message):
    player.send_message(bot, venue_message, [])

    loc = gamedata._map[player._location_id]
    event_id = loc.get_random_event(venue_option)
    if event_id not in gamedata._texts:
        player.send_message(bot, u"no data for event: {}".format(event_id),
                            get_show_venues_keyboard(player, gamedata))
        return
    #TODO: ensure event_id is always present in texts
    text_id = random.choice(gamedata._texts[event_id].keys())
    descr, options = gamedata._texts[event_id][text_id]
    if len(options) == 1:
        do_get_outcome(player, bot, gamedata, event_id, text_id, options.keys()[0], True)
        return

    message = descr
    keyboard = list()
    for option_text, outcomes in options.iteritems():
        action = Act("GETOUTCOME", event_id, text_id, option_text, False)
        keyboard.append([(action, option_text)])
    player.send_message(bot, message, keyboard)


def do_go(player, bot, gamedata, dir_id):
    loc = gamedata._map[player._location_id]
    transition = loc._adjacent.get(dir_id)
    player.send_message(bot, transition._descr, [])
    if can_go(dir_id, loc._adjacent, gamedata):
        player._location_id = transition._to_id
    do_show_map(player, bot, gamedata)


def do_continue(player, bot, gamedata):
    do_show_map(player, bot, gamedata)


def do_nothing(player, bot, gamedata):
    return


ACTIONS = {
    "GO": do_go,
    "SHOWMAP": do_show_map,
    "SHOWVENUES": do_show_venues,
    "VENUEACTION": do_venue_action,
    "GETOUTCOME": do_get_outcome,
    "CONTINUE": do_continue,
    "SUPERMIND": do_nothing,
    "LAB": do_nothing,
    "AVATAR": do_nothing
}

START_LOCATION_ID = "001"

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
                text="Failed to load gamedata. Details: {}".format(e.message))
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
        player.do_action(text, bot, self._gamedata)


def run_main_loop(token, credentials, spreadsheet_id):
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="load_log.tsv")
    gamedata = load_gamedata(credentials, spreadsheet_id)
    logging.info(get_gamedata_status(gamedata).encode("utf8"))

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO, filename="log.tsv")
    updater = Updater(token=token)
    dispatcher = updater.dispatcher

    players = dict()

    handlers = [
        CommandHandler("start", StartCommandHandlerCallback(players)),
        CommandHandler("reload", ReloadCommandHandlerCallback(players,
                        gamedata, credentials, spreadsheet_id)),
        MessageHandler(Filters.text, TextHandlerCallback(players, gamedata))
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
