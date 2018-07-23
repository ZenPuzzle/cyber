#coding: utf8
import random

class Act(object):

    def __init__(self, name, *args):
        self._name = name
        self._args = args


MAP_KEYBOARD = [
    [("SUPERMIND", u"🌐"), (Act("GO", "NW"), u"↖️"), (Act("GO", "N"), u"⬆️"), (Act("GO", "NE"), u"↗️")],
    [("LAB", u"🗺"), (Act("GO", "W"), u"◀️"), ("SHOWVENUES", u"🔄"), (Act("GO", "E"), u"▶️")],
    [("AVATAR", u"🤡"), (Act("GO", "SW"), u"↙️"), (Act("GO", "S"), u"⬇️"), (Act("GO", "SE"), u"↘️")]
]


def make_pretty_button(action, button, adj):
    if type(action) == str:
        return button
    dir_id = action._args[0]
    return adj[dir_id]._arrow + adj[dir_id]._extra_button_markup


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
    message = u" ".join(message_parts) + u"\n"
    outcome_id = outcome._outcome_id
    if outcome_id is not None:
        if outcome_id.startswith("i_"):
            if outcome_id not in gamedata._items:
                player.send_message(bot, u"Unknown item: {}".format(outcome_id))
            else:
                message += u"...\n{} ({}) /view_{}".format(
                    gamedata._items[outcome_id]._name, outcome._cnt, outcome_id)
        else:
            message += outcome_id
    keyboard = get_show_venues_keyboard(player, gamedata)
    player.send_message(bot, message.encode("utf8"), keyboard)


def do_venue_action(player, bot, gamedata, venue_option, venue_message):
    player.send_message(bot, venue_message, [])

    loc = gamedata._map[player._location_id]

    outcomes = loc._venue_option2events[venue_option]
    event_id = choose_outcome(outcomes)
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


def can_go(dir_id, adj, gamedata):
    return (dir_id in adj) and (adj[dir_id]._to_id in gamedata._map) and adj[dir_id]._multiplier > 0


def do_go(player, bot, gamedata, dir_id):
    loc = gamedata._map[player._location_id]
    transition = loc._adjacent.get(dir_id)
    if can_go(dir_id, loc._adjacent, gamedata):
#        player.set_delayed_action(bot, transition._multiplier, Act("CHANGELOC", transition._to_id))
#        keyboard = [
#            [(Act("CANCEL", Act("SHOWMAP")), u"Отмена")]
#        ]
        player.send_message(bot, transition._descr)
        do_change_location(player, bot, gamedata, transition._to_id)
        return
    player.send_message(bot, transition._descr)


def do_continue(player, bot, gamedata):
    do_show_map(player, bot, gamedata)


def do_nothing(player, bot, gamedata):
    return


def do_change_location(player, bot, gamedata, to_loc_id):
    player._location_id = to_loc_id
    do_show_map(player, bot, gamedata)


def do_cancel(player, bot, gamedata, prev_action):
    player._delayed_action = None
    player._fullfill_time = None
    player.do_action(prev_action, bot, gamedata)


ACTIONS = {
    "GO": do_go,
    "SHOWMAP": do_show_map,
    "SHOWVENUES": do_show_venues,
    "VENUEACTION": do_venue_action,
    "GETOUTCOME": do_get_outcome,
    "CONTINUE": do_continue,
    "SUPERMIND": do_nothing,
    "LAB": do_nothing,
    "AVATAR": do_nothing,
    "CHANGELOC": do_change_location,
    "CANCEL": do_cancel
}
