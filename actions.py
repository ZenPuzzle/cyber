# coding: utf8
import random
import time
import logging

from db import send_message, update_player

from constants import *

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
    text = text + u"\nИсследовано {}%".format(player._research_percent[player._location_id])
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
    researched = player._research_percent.get(player._location_id, 0)
    keyboard = [
        [SUPERMIND, LAB, AVATAR, (("SHOWMAP",), u"🔄")]
    ]
    for venue_id, _, research_threshold in loc._venues:
        if venue_id in gamedata._venues and researched >= research_threshold:
            keyboard.append([
                (("SHOWVENUE", venue_id),
                 gamedata._venues[venue_id]._name)
            ])
    if loc._events:
        keyboard.append([
            (("EXPLORE",), u"Побродить по окрестностям")
        ])
    return keyboard


def do_show_venue(player, bot, gamedata, pdb, venue_id):
    loc = gamedata._map[player._location_id]
    keyboard = [
        [SUPERMIND, LAB, AVATAR, (("SHOWMAP",), u"🔄")]
    ]
    text = ""
    for vid, venue_descr, _ in loc._venues:
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
    text = text + u"\nИсследовано {}%".format(player._research_percent[player._location_id])
    keyboard = get_show_venues_keyboard(player, gamedata)
    with pdb.connect() as conn:
        send_message(player, conn, bot, text, keyboard)


def choose_outcome(outcomes):
    p = random.random()
    for accu_prob, outcome in outcomes:
        if p < accu_prob:
            return outcome
    assert False, "bad probabilities"


def do_get_outcome(player, bot, gamedata, pdb, event_id, text_id, option_text,
                   show_descr, lore_gained):
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
                item = gamedata._items[outcome_id]
                message += u"...\nНаходка! {} ({}) /view_{}".format(
                    item._name, outcome._cnt, outcome_id
                )
                backpack = player._avatar._backpack
                free_weight= backpack._max_weight - backpack.get_weight(gamedata)
                taken_count = int(min(free_weight / item._weight, outcome._cnt))
                if taken_count > 0:
                    backpack.insert_item(outcome_id, taken_count)
                    message += u"\n{} ({}) помещён(-а) в рюкзак".format(
                        item._name, taken_count
                    )
                if taken_count < outcome._cnt:
                    message += u"\n{} {} не поместился(-ась) в рюкзак".format(
                        outcome._cnt - taken_count, item._name
                    )
                lore_for_new_item = player.get_lore_for_new_entity(outcome_id, gamedata)
                if lore_for_new_item > 0:
                    message += u"\nПолучено {} ЗМ за находку".format(lore_for_new_item)
        else:
            message += outcome_id
    if lore_gained > 0:
        message += u"\nПолучено {} ЗМ за исследование".format(lore_gained)
    keyboard = get_show_venues_keyboard(player, gamedata)
    with pdb.connect() as conn:
        update_player(player, conn)
        send_message(player, conn, bot, message, keyboard)


def resolve_event(player, bot, gamedata, pdb, event_id, lore_gained):
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
                       options.keys()[0], True, lore_gained)
        return

    message = descr
    keyboard = list()
    for option_text, outcomes in options.iteritems():
        action = ("GETOUTCOME", event_id, text_id, option_text, False, lore_gained)
        keyboard.append([(action, option_text)])

    with pdb.connect() as conn:
        send_message(player, conn, bot, message, keyboard)


def do_explore(player, bot, gamedata, pdb):
    loc = gamedata._map[player._location_id]
    venue_id = choose_outcome(loc._events)
    if venue_id not in gamedata._venues:
        bot.send_message(player._chat_id, "Missing venue {}".format(venue_id.encode("utf8")))
        logging.error("Missing venue {}".format(venue_id.encode("utf8")))
        return

    researched = min(loc._research_rate, 100 - player._research_percent[player._location_id])
    lore_gained = int(researched * 0.1 * player.get_cpu())
    if researched > 0:
        with pdb.connect() as conn:
            player.update_lore(gamedata)
            player._raw_lore += lore_gained
            player._lore_last_update = time.time()
            player._research_percent[player._location_id] += researched
            update_player(player, conn)

    event_id = choose_outcome(gamedata._venues[venue_id]._events)
    resolve_event(player, bot, gamedata, pdb, event_id, lore_gained)


def do_venue_action(player, bot, gamedata, pdb, venue_option, venue_message):
    with pdb.connect() as conn:
        send_message(player, conn, bot, venue_message, [])

    loc = gamedata._map[player._location_id]
    outcomes = loc._venue_option2events[venue_option]
    event_id = choose_outcome(outcomes)
    resolve_event(player, bot, gamedata, pdb, event_id, 0)


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
        player.set_location(to_loc_id)
        try:
            update_player(player, conn)
        except Exception as e:
            player.set_location(cur_loc_id)
            raise e
    do_show_map(player, bot, gamedata, pdb)


def do_cancel(player, bot, gamedata, pdb, prev_action):
    player.do_action(prev_action, bot, gamedata, pdb)


def day(cnt):
    rest = cnt % 10
    if rest == 1:
        return u"день"
    if 1 < rest < 5:
        return u"дня"
    return u"дней"


def hour(cnt):
    rest = cnt % 10
    if rest == 1:
        return u"час"
    if 1 < rest < 5:
        return u"часа"
    return u"часов"


def minute(cnt):
    rest = cnt % 10
    if rest == 1:
        return u"минута"
    if 1 < rest < 5:
        return u"минуты"
    return u"минут"


def second(cnt):
    rest = cnt % 10
    if rest == 1:
        return u"секунда"
    if 1 < rest < 5:
        return u"секунды"
    return u"секунд"


def format_time(seconds):
    seconds = int(seconds)
    days = seconds / 3600 / 24
    hours = seconds % (3600 * 24) / 3600
    mins = seconds % 3600 / 60
    seconds = seconds % 60
    parts = []
    if days > 0:
        parts.append(u"{} {}".format(days, day(days)))
    if hours > 0 or days > 0:
        parts.append(u"{} {}".format(hours, hour(hours)))
    if mins > 0 or hours > 0 or days > 0:
        parts.append(u"{} {}".format(mins, minute(mins)))
    parts.append(u"{} {}".format(seconds, second(seconds)))
    return u", ".join(parts)


def do_show_mind(player, bot, gamedata, pdb):
    with pdb.connect() as conn:
        player.update_lore(gamedata)
        update_player(player, conn)
        text = u"{}\nЗнание Мира: {}\nСырое ЗМ: {}".format(
            player.get_name(), player._lore, player._raw_lore
        )
        if player._raw_lore > 0:
            text += u", время обработки: {}\n".format(
                format_time(player._raw_lore * 1. / player.get_cpu() * 60)
            )
        else:
            text += u"\n"
        text += u"""Использование памяти: {} / {}\nЗагрузка CPU: {} / {}\n""".format(
                player.get_used_ram(gamedata), player.get_ram(),
                player.get_used_cpu(gamedata), player.get_cpu()
                )
        text += u"Запущенных программ: {}\n".format(len(player._running_soft))
        text += u"Скомпилированных программ: {}\n".format(len(player._installed_soft))
        text += u"Новых программ: {} /software".format(
            len(gamedata._programs)
        )
        if player._compiling_soft != []:
            program = gamedata._programs[player._compiling_soft[0]]
            cpu, start_time = player._compiling_soft[1:3]
            ts = time.time()
            progress = (ts - start_time) / (program._compile_time / cpu * TICK_DURATION)
            progress = int(progress * 100)
            text += u"\nКомпиляция {} выполнена на {}%".format(program._name, progress)
        send_message(player, conn, bot, text)


def do_show_software(player, bot, gamedata, pdb):
    with pdb.connect() as conn:
        player.update_lore(gamedata)
        update_player(player, conn)
    text = u""
    if player._running_soft:
        text += u"Запущенные программы:\n"
        for program_id in player._running_soft:
            text += gamedata._programs[program_id]._name + u" /view_{} /stop_{}\n".format(program_id, program_id)
        text += u"\n"
    if player._installed_soft:
        text += u"Скомпилированные программы:\n"
        for program_id in player._installed_soft:
            text += gamedata._programs[program_id]._name + u" /view_{} /run_{}\n".format(program_id, program_id)
        text += u"\n"
    text += u"Новые программы:\n"
    for program_id in gamedata._programs:
        if program_id not in player._running_soft and (len(player._compiling_soft) == 0 or player._compiling_soft[0] != program_id) and program_id not in player._installed_soft:
            text += gamedata._programs[program_id]._name + u" /view_{} /compile_{}\n".format(program_id, program_id)
    bot.send_message(player._chat_id, text)


def do_compile_program(player, bot, gamedata, pdb, program_id):
    with pdb.connect() as conn:
        player.update_lore(gamedata)
        update_player(player, conn)
        if player._compiling_soft != []:
            bot.send_message(player._chat_id, u"Другая программа ещё компилируется")
        else:
            if player.compile_program(program_id, gamedata):
                update_player(player, conn)
                send_message(player, conn, bot,
                            u"Компилирую {}".format(gamedata._programs[program_id]._name))
            else:
                bot.send_message(player._chat_id,
                                 u"Недостаточно ЦП для начала компиляции")


def do_run_program(player, bot, gamedata, pdb, program_id):
    with pdb.connect() as conn:
        player.update_lore(gamedata)
        update_player(player, conn)
        if program_id not in player._installed_soft:
            bot.send_message(player._chat_id, u"Нужно сперва скомпилировать программу")
            return
        program = gamedata._programs[program_id]
        cpu_ok = (player.get_cpu() - player.get_used_cpu(gamedata)) >= program._cpu_usage
        ram_ok = (player.get_ram() - player.get_used_ram(gamedata)) >= program._ram_usage
        if cpu_ok and ram_ok:
            player._running_soft.add(program_id)
            player._installed_soft.remove(program_id)
            update_player(player, conn)
            bot.send_message(player._chat_id,
                             u"Запускаю {}".format(gamedata._programs[program_id]._name))
        else:
            text = u"Не удалось запустить программу\n"
            if not cpu_ok:
                text += u"Недостаточно CPU\n"
            if not ram_ok:
                text += u"Недостаточно свободной памяти\n"
            bot.send_message(player._chat_id, text)


def do_stop_program(player, bot, gamedata, pdb, program_id):
    with pdb.connect() as conn:
        player.update_lore(gamedata)
        update_player(player, conn)
        program = gamedata._programs.get(program_id)
        if program is None:
            return
        if program_id not in player._running_soft:
            bot.send_message(player._chat_id,
                             u"Программа {} не запущена".format(program._name))
            return
        player._running_soft.remove(program_id)
        player._installed_soft.add(program_id)
        update_player(player, conn)
        bot.send_message(player._chat_id,
                         u"Программа {} остановлена".format(program._name))


def do_view_info(player, bot, gamedata, pdb, entity_id):
    text = None
    if entity_id in gamedata._items:
        text = gamedata._items[entity_id].get_info()
    elif entity_id in gamedata._programs:
        text = gamedata._programs[entity_id].get_info()
    if text is not None:
        bot.send_message(player._chat_id, text)


def do_view_avatar(player, bot, gamedata, pdb):
    backpack = player._avatar._backpack
    message = u"Предметы в рюкзаке:\n"
    for item, count in backpack._items:
        message += u"{} ({}) /view_{}\n".format(gamedata._items[item]._name, count, item)
    weight = backpack.get_weight(gamedata)
    message += u"Вес: {} / {}".format(weight, backpack._max_weight)
    bot.send_message(player._chat_id, message)


ACTIONS = {
    "GO": do_go,
    "SHOWMAP": do_show_map,
    "SHOWVENUES": do_show_venues,
    "SHOWVENUE": do_show_venue,
    "VENUEACTION": do_venue_action,
    "GETOUTCOME": do_get_outcome,
    "CONTINUE": do_continue,
    "SUPERMIND": do_show_mind,
    "LAB": do_nothing,
    "AVATAR": do_view_avatar,
    "CHANGELOC": do_change_location,
    "CANCEL": do_cancel,
    "EXPLORE": do_explore
}

COMMANDS = {
    "/compile": do_compile_program,
    "/software": do_show_software,
    "/run": do_run_program,
    "/view": do_view_info,
    "/stop": do_stop_program
}
