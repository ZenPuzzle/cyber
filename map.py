#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
from xml.etree import ElementTree as ET
import logging
import random
import json
import argparse
import ConfigParser as configparser

from httplib2 import Http
from apiclient.discovery import build
from oauth2client import file, client, tools

XML_NS = {
    "xls": "urn:schemas-microsoft-com:office:spreadsheet"
}

DIR2DIR_ID = {
    u"север": "N",
    u"СВ": "NE",
    u"восток": "E",
    u"ЮВ": "SE",
    u"юг": "S",
    u"ЮЗ": "SW",
    u"запад": "W",
    u"СЗ": "NW",
    u"ВЕРХ": "U",
    u"НИЗ": "D"
}

class Position(object):

    def __init__(self, x = 0, y = 0, z = 0):
        self._x = x
        self._y = y
        self._z = z

    def __str__(self):
        return "({}, {}, {})".format(self._x, self._y, self._z)

class Transition(object):

    def __init__(self, to_id, descr, multiplier, arrow, extra_button_markup):
        self._to_id = to_id
        self._descr = descr
        self._multiplier = multiplier
        self._arrow = arrow
        self._extra_button_markup = extra_button_markup


def get_cell_data(row):
    cells = row.findall("xls:Cell", XML_NS)
    if not cells:
        return
    return [cell.find("xls:Data", XML_NS) for cell in cells]


class Location(object):
    """
    descr: unicode
    size: float
    research_rage: float
    pos: Position
    adjacent: list of (dir_id, Transition)
    venues: list of venue_ids
    venue_option2events: unicode -> events dict
    """

    def __init__(self, id, descr, size, research_rate, pos, adjacent, venues, events):
        self._id = id
        self._descr = descr
        self._size = size
        self._research_rate = research_rate
        self._pos = pos
        self._adjacent = adjacent
        self._venues = venues
        self._events = events
        self._venue_option2events = dict()

    @staticmethod
    def parse_from_sheet(worksheet):
        rows = worksheet["values"]
        assert len(rows) > 19

        assert rows[0] == [u"глобальная карта", u"основное"]

        descr = rows[1][0]
        assert descr

        assert rows[2][0] == u"размер квадрата"
        size = float(rows[2][1])
        assert rows[2][2] == u"скорость исследования"
        research_rate = float(rows[2][3])

        assert rows[3][0] == u"X"
        x = float(rows[3][1])
        assert rows[4][0] == u"Y"
        y = float(rows[4][1])

        assert rows[6][:5] == [
            u"выходы",
            u"условие",
            u"переход на",
            u"множитель",
            u"описание процесса перехода"
        ]
        adjacent = dict()
        for row_index in range(7, 15):
            row = rows[row_index]
            assert len(row) >= 6
            dir_id = DIR2DIR_ID[row[0]]
            to_id = row[2]
            multiplier = float(row[3])
            journey_descr = row[4]
            arrow = row[5]
            extra_button_markup = row[6] if len(row) >= 7 else u""
            adjacent[dir_id] = Transition(to_id, journey_descr, multiplier,
                                          arrow, extra_button_markup)

        assert rows[17][0] == u"постоянные объекты"
        row_index = 18
        venues = list()
        while row_index < len(rows) and rows[row_index][0] != u"случайные ивенты":
            row = rows[row_index]
            if len(row) >= 3:
#                object_name, prob, object_descr = row[:3]
#                assert prob.endswith("%")
#                prob = int(prob[:-1]) * 0.1
                venues.append(row[0])
            row_index += 1

        events = list()
        if row_index < len(rows):
            row_index += 1
            while row_index < len(rows):
                row = rows[row_index]
                if len(row) >= 2:
                    event_name, prob = row[:2]
                    assert prob.endswith("%")
                    prob = int(prob[:-1]) * 0.01
                    events.append((prob, event_name))
                row_index += 1
        return Location("", descr, size, research_rate, Position(x, y), adjacent, venues, events)

class Venue(object):
    """
    options - dict of (descr, message, events)
        events is a sorted list of (accu prob, event_id)
    """

    def __init__(self, name, options):
        self._name = name
        self._options = options


def accumulate_probs(events):
    result = list()
    acc_prob = 0
    for prob, event_data in sorted(events, reverse=True):
        acc_prob += prob
        result.append((acc_prob, event_data))
    assert abs(1 - acc_prob) < 0.001, "invalid accumulated prob"
    return result


def load_venues(sheet_data):
    rows = sheet_data["values"]
    row_index = 1
    venues = dict()
    while row_index < len(rows):
        assert len(rows[row_index]) == 1, "venue id expected, found: {}".format(" ".join(row))
        venue_id = rows[row_index][0]
        row_index += 1
        while row_index < len(rows) and len(rows[row_index]) > 1:
            row = rows[row_index]
            assert row[2] != "" or row[1] == u"исследование", "expected venue option or research section"
            venue_name = row[1]

            options = list()
            while row_index < len(rows) and len(rows[row_index]) > 1 and (rows[row_index][1] in {venue_name, u""}):
                row = rows[row_index]
                option_text = row[2]
                option_message = row[3] if row[3] else u"Исследуем"

                events = list()
                while row_index < len(rows) and len(rows[row_index]) > 1 and (rows[row_index][1] in {venue_name, u""}) and (rows[row_index][2] in {option_text, u""}):
                    row = rows[row_index]
                    if len(row) >= 7:
                        events.append((float(row[5].strip("%")) * 0.01, row[6]))
                    row_index += 1

                options.append((option_text, option_message, accumulate_probs(events)))
            if venue_name != u"исследование":
                if venue_id in venues:
                    logging.warning("duplicate venue id: {}, row: {}".format(venue_id.encode("utf8"), u" ".join(rows[row_index]).encode('utf8')))
                venues[venue_id] = Venue(venue_name, options)
    return venues


class TextQuestOutcome(object):

    def __init__(self, cnt, message, outcome_id):
        self._cnt = cnt
        self._message = message
        self._outcome_id = outcome_id


def load_texts(sheet_data):
    rows = sheet_data["values"]
    row_index = 1
    event_id2texts = dict()
    while row_index < len(rows):
        event_id = rows[row_index][1]
        if event_id in event_id2texts:
            logging.warning("duplicate event_id {} in row {}".format(event_id.encode("utf8"), row_index))
        event_id2texts[event_id] = dict()
        row_index += 1

        while row_index < len(rows) and len(rows[row_index]) > 2:
            text_id, text = rows[row_index][:2]
            assert text_id not in event_id2texts[event_id]
            event_id2texts[event_id][text_id] = (text, dict())

            while row_index < len(rows) and len(rows[row_index]) > 2 and (rows[row_index][0] in {text_id, u""}):
                option_text = rows[row_index][5]
                assert option_text not in event_id2texts[event_id][text_id]

                outcomes = list()
                while row_index < len(rows) and len(rows[row_index]) > 2 and (rows[row_index][0] in {text_id, u""}) and (rows[row_index][5] in {option_text, u""}):
                    row = rows[row_index]
                    if len(row) >= 6 and row[6]:
                        prob = float(row[6].strip("%")) * 0.01
                        cnt = int(row[7]) if len(row) >= 8 and row[7] else None
                        message = row[8] if len(row) >= 9 else ""
                        outcome_id = row[9] if len(row) >= 10 else None
                        if outcome_id is not None and outcome_id.startswith("i_") and (cnt is None or cnt == 0):
                            logging.warning(u"Bad item count in row #{}: {}".format(row_index, cnt).encode("utf8"))
                        if prob > 0:
                            outcomes.append((prob, TextQuestOutcome(cnt, message, outcome_id)))
                    row_index += 1
                event_id2texts[event_id][text_id][1][option_text] = accumulate_probs(outcomes)
    return event_id2texts


class Event(object):
    """
    descr - event descr unicode
    options - option descr -> outcomes mapping, outcomes is a list of
            (accumulated probability, descr, outcome_id)
    """

    def __init__(self, descr, options):
        self._descr = descr
        self._options = options


class Item(object):

    def __init__(self, name, descr, weight):
        self._name = name
        self._descr = descr
        self._weight = weight

    def get_info(self):
        return u"{}\n{}\nВес: {}".format(self._name, self._descr, self._weight)


def load_items(sheet_data):
    rows = sheet_data["values"]
    items = dict()
    row_index = 2
    while row_index < len(rows):
        row = rows[row_index]
        if row[0]:
            item_id = row[0]
            if item_id in items:
                logging.warning("duplicate item id {} in row {}".format(
                                item_id.encode("utf8"), row_index))
            items[item_id] = Item(row[1], row[2], float(row[3]))
        row_index += 1
    return items


class GameData(object):
    """
        map: location_id -> Location dict
        venues: venue_id -> Venue dict
    """

    def __init__(self, game_map, venues, texts, items):
        self._map = game_map
        self._venues = venues
        self._texts = texts
        self._items = items
        for loc_id in game_map:
            venue_option2events = dict()
            for venue_id in game_map[loc_id]._venues:
                if venue_id not in self._venues:
                    logging.warning("Skipping unknown venue: {}".format(venue_id.encode("utf8")))
                    continue
                venue = self._venues[venue_id]
                for option, _, events in venue._options:
                    venue_option2events[option] = events
            game_map[loc_id]._venue_option2events = venue_option2events

    def update(self, gamedata):
        self.__init__(gamedata._map, gamedata._venues, gamedata._texts)


def load_spreadsheets(credentials_filename, spreadsheet_id):
    store = file.Storage(credentials_filename)
    creds = store.get()
    service = build('sheets', 'v4', http=creds.authorize(Http()))
    request = service.spreadsheets().get(spreadsheetId=spreadsheet_id,
                                         ranges=[], includeGridData=False)
    response = request.execute()
    sheet_data = dict()
    for sheet in response["sheets"]:
        title = sheet["properties"]["title"]
        sheet_data[title] = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=title).execute()
    return response, sheet_data


def check_gamedata(gamedata):
    missing_locations, missing_venues, missing_texts, missing_items = set(), set(), set(), set()
    for loc in gamedata._map.itervalues():
        for adj in loc._adjacent.itervalues():
            if adj._to_id not in gamedata._map:
                missing_locations.add(adj._to_id)
        for venue in loc._venues:
            if venue not in gamedata._venues:
                missing_venues.add(venue)
        for events in loc._venue_option2events.itervalues():
            for _, event_id in events:
                if event_id not in gamedata._texts:
                    missing_texts.add(event_id)
    for event in gamedata._texts:
        for text_id in gamedata._texts[event]:
            for _, outcomes in gamedata._texts[event][text_id][1].iteritems():
                for _, outcome in outcomes:
                    if outcome._outcome_id is not None and outcome._outcome_id.startswith("i_"):
                        if outcome._outcome_id not in gamedata._items:
                            missing_items.add(outcome._outcome_id)
    return sorted(missing_locations), sorted(missing_venues), sorted(missing_texts), sorted(missing_items)


def get_gamedata_status(gamedata):
    missing_loc, missing_venues, missing_texts, missing_items = check_gamedata(gamedata)
    return u"\n".join([
        u"Status check.",
        u"Missing locations:",
        u", ".join(missing_loc),
        u"Missing venues:",
        u", ".join(missing_venues),
        u"Missing texts:",
        u", ".join(missing_texts),
        u"Missing items:",
        u", ".join(missing_items)
    ])


def load_gamedata(credentials_filename, spreadsheet_id):
    spreadsheets_info, sheet2data = load_spreadsheets(credentials_filename, spreadsheet_id)

    game_map = dict()
    for title, data in sheet2data.iteritems():
        assert title not in game_map
        if title.isnumeric():
            location = Location.parse_from_sheet(data)
            location._id = title
            if location is not None:
                game_map[location._id] = location
    location_names = u", ".join(sorted(list(game_map.iterkeys()))).encode("utf8")
    logging.info("loaded {} locations: {}".format(len(game_map), location_names))

    venues = load_venues(sheet2data[u"локации"])
    venue_names = u", ".join(sorted(list(venues.iterkeys()))).encode("utf8")
    logging.info("loaded {} venues: {}".format(len(venues), venue_names))

    texts = load_texts(sheet2data[u"тексты"])
    logging.info("loaded {} texts".format(len(texts)))

    items = load_items(sheet2data[u"Ресурсы"])
    return GameData(game_map, venues, texts, items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = configparser.RawConfigParser()
    cfg.read(args.cfg)

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    gamedata = load_gamedata(cfg.get("auth", "credentials"), cfg.get("gamedata", "spreadsheet_id"))
    logging.info(get_gamedata_status(gamedata))
