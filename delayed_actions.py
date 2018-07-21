from heapq import heappop
import time

def run_routine(bot, players, gamedata):
    while True:
        if not bot.delayed_actions:
            time.sleep(0.01)
            continue
        with bot.delayed_action_lock:
            ts, count, player_id = bot.delayed_actions[0]
            if ts > time.time():
                continue
            heappop(bot.delayed_actions)
        action = players[player_id]._delayed_action
        print action
        if action is None:
            continue
        fullfill_time = players[player_id]._fullfill_time
        print fullfill_time
        if fullfill_time is None:
            continue
        if fullfill_time != ts:
            assert fullfill_time > ts
            continue
        players[player_id].do_action(action, bot, gamedata)
