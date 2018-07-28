#coding: utf8
import random

from db import send_message, update_player

SUPERMIND = (("SUPERMIND",), u"🌐")
LAB = (("LAB",), u"🗺")
AVATAR = (("AVATAR",), u"🤡")


def get_map_keyboard_item(dir_id, adj):
    return (("GO", dir_id), adj[dir_id]._arrow + adj[dir_id]._extra_button_markup)


def get_map_keyboard(dir_ids, adj):
    return [get_map_keyboard_item(dir_id, adj) for dir_id in dir_ids]


def do_show_map(player, bot, gamedata, pdb):
    loc = gamedata._map[player._location_id]
    text = player._location_id + u" " + loc._descr
    adj = loc._adjacent

    keyboard = [
        [SUPERMIND] + get_map_keyboard(["NW", "N", "NE"], adj),
        [LAB, get_map_keyboard_item("W", adj), (("SHOWVENUES",), u"🔄"), get_map_keyboard_item("E", adj)],
        [AVATAR] + get_map_keyboard(["SW", "S", "SE"], adj)
    ]
    with pdb.connect() as conn:
        send_message(player, conn, bot, text, keyboard)


def get_show_venues_keyboard(player, gamedata):
    loc = gamedata._map[player._location_id]
    keyboard = [
        [SUPERMIND, LAB, AVATAR, (("SHOWMAP",), u"🔄")]
    ]
    for venue_id, _ in loc._venues:
        if venue_id in gamedata._venues:
            keyboard.append([
                (("SHOWVENUE", venue_id),
                 gamedata._venues[venue_id]._name)
            ])
    return keyboard


def do_show_venue(player, bot, gamedata, pdb, venue_id):
    loc = gamedata._map[player._location_id]
    keyboard = [
        [SUPERMIND, LAB, AVATAR, (("SHOWMAP",), u"🔄")]
    ]
    text = ""
    for vid, venue_descr in loc._venues:
        if vid == venue_id:
            text = venue_descr
            for option in gamedata._venues[venue_id]._options:
                keyboard.append([(("VENUEACTION", option[0], option[1]), option[0])])
    keyboard.append([(("SHOWVENUES",), u"Назад")])
    with pdb.connect() as conn:
        send_message(player, conn, bot, text, keyboard)


def do_show_venues(player, bot, gamedata, pdb):
    loc = gamedata._map[player._location_id]
    text = player._location_id + u" " + loc._descr
    keyboard = get_show_venues_keyboard(player, gamedata)
    with pdb.connect() as conn:
        send_message(player, conn, bot, text, keyboard)


def choose_outcome(outcomes):
    p = random.random()
    for accu_prob, outcome in outcomes:
        if p < accu_prob:
            return outcome
    assert False, "bad probabilities"


def do_get_outcome(player, bot, gamedata, pdb, event_id, text_id, option_text, show_descr):
    descr, options = gamedata._texts[event_id][text_id]
    outcome = choose_outcome(options[option_text])
    message_parts = list()
    if show_descr:
        message_parts.append(descr)
    if outcome._message:
        message_parts.append(outcome._message)
    message = u" ".join(message_parts) + u"\n"
    outcome_id = outcome._outcome_id
    if outcome_id is not None:
        if outcome_id.startswith("i_"):
            if outcome_id not in gamedata._items:
                bot.send_message(player._chat_id, u"Unknown item: {}".format(outcome_id))
            else:
                message += u"...\n{} ({}) /view_{}".format(
                    gamedata._items[outcome_id]._name, outcome._cnt, outcome_id)
        else:
            message += outcome_id
    keyboard = get_show_venues_keyboard(player, gamedata)
    with pdb.connect() as conn:
        send_message(player, conn, bot, message, keyboard)


def do_venue_action(player, bot, gamedata, pdb, venue_option, venue_message):
    with pdb.connect() as conn:
        send_message(player, conn, bot, venue_message, [])

    loc = gamedata._map[player._location_id]
    outcomes = loc._venue_option2events[venue_option]
    event_id = choose_outcome(outcomes)
    if event_id not in gamedata._texts:
        logging.warning(u"no data for event: {}".format(event_id).encode("utf8"))
        with pdb.connect() as conn:
            send_message(player, conn, bot,
                         u"no data for event: {}".format(event_id),
                         get_show_venues_keyboard(player, gamedata))
        return

    text_id = random.choice(gamedata._texts[event_id].keys())
    descr, options = gamedata._texts[event_id][text_id]
    if len(options) == 1:
        do_get_outcome(player, bot, gamedata, pdb, event_id, text_id,
                       options.keys()[0], True)
        return

    message = descr
    keyboard = list()
    for option_text, outcomes in options.iteritems():
        action = ("GETOUTCOME", event_id, text_id, option_text, False)
        keyboard.append([(action, option_text)])

    with pdb.connect() as conn:
        send_message(player, conn, bot, message, keyboard)


def can_go(dir_id, adj, gamedata):
    return (dir_id in adj) and (adj[dir_id]._to_id in gamedata._map) and adj[dir_id]._multiplier > 0


def do_go(player, bot, gamedata, pdb, dir_id):
    loc = gamedata._map[player._location_id]
    transition = loc._adjacent.get(dir_id)
    bot.send_message(player._chat_id, transition._descr)
    if can_go(dir_id, loc._adjacent, gamedata):
#        player.set_delayed_action(bot, transition._multiplier, Act("CHANGELOC", transition._to_id))
#        keyboard = [
#            [(Act("CANCEL", Act("SHOWMAP")), u"Отмена")]
#        ]
        do_change_location(player, bot, gamedata, pdb, transition._to_id)
        return


def do_continue(player, bot, gamedata, pdb):
    do_show_map(player, bot, gamedata, pdb)


def do_nothing(player, bot, gamedata, pdb):
    return


def do_change_location(player, bot, gamedata, pdb, to_loc_id):
    cur_loc_id = player._location_id
    with pdb.connect() as conn:
        player._location_id = to_loc_id
        try:
            update_player(player, conn)
        except Exception as e:
            player._location_id = cur_loc_id
            raise e
    do_show_map(player, bot, gamedata, pdb)


def do_cancel(player, bot, gamedata, pdb, prev_action):
    player.do_action(prev_action, bot, gamedata, pdb)


ACTIONS = {
    "GO": do_go,
    "SHOWMAP": do_show_map,
    "SHOWVENUES": do_show_venues,
    "SHOWVENUE": do_show_venue,
    "VENUEACTION": do_venue_action,
    "GETOUTCOME": do_get_outcome,
    "CONTINUE": do_continue,
    "SUPERMIND": do_nothing,
    "LAB": do_nothing,
    "AVATAR": do_nothing,
    "CHANGELOC": do_change_location,
    "CANCEL": do_cancel
}
