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

    def get_random_event(self, venue_option):
        p = random.random()
        for accu_prob, event_id in self._venue_option2events[venue_option]:
            logging.info("p: {}, accu_prob: {}".format(p, accu_prob))
            if p < accu_prob:
                return event_id
        assert False, "bad event probabilites"

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
    options - dict of (descr, events)
        events is a sorted list of (accu prob, event_id)
    """

    def __init__(self, name, options):
        self._name = name
        self._options = options


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

                events = list()
                while row_index < len(rows) and len(rows[row_index]) > 1 and (rows[row_index][1] in {venue_name, u""}) and (rows[row_index][2] in {option_text, u""}):
                    row = rows[row_index]
                    if len(row) >= 6:
                        events.append((float(row[4].strip("%")) * 0.01, row[5]))
                    row_index += 1

                acc_prob = 0
                options.append((option_text, list()))
                for prob, event_id in sorted(events, reverse=True):
                    acc_prob += prob
                    options[-1][1].append((acc_prob, event_id))
                    logging.info("{} {}".format(acc_prob, event_id.encode("utf8")))
                assert abs(1 - acc_prob) < 0.001, "invalid accumulated prob for venue {}".format(venue_id.encode("utf8"))
            if venue_name != u"исследование":
                assert venue_id not in venues, "duplicate venue id: {}, row: {}".format(venue_id.encode("utf8"), u" ".join(rows[row_index]).encode('utf8'))
                venues[venue_id] = Venue(venue_name, options)
    return venues


class Event(object):
    """
    descr - event descr unicode
    options - option descr -> outcomes mapping, outcomes is a list of
            (accumulated probability, descr, outcome_id)
    """

    def __init__(self, descr, options):
        self._descr = descr
        self._options = options


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


class GameData(object):
    """
        map: location_id -> Location dict
        venues: venue_id -> Venue dict
    """

    def __init__(self, game_map, venues):
        self._map = game_map
        self._venues = venues
        for loc_id in game_map:
            venue_option2events = dict()
            for venue_id in game_map[loc_id]._venues:
                if venue_id not in self._venues:
                    logging.warning("Skipping unknown venue: {}".format(venue_id.encode("utf8")))
                    continue
                venue = self._venues[venue_id]
                for option, events in venue._options:
                    venue_option2events[option] = events
            game_map[loc_id]._venue_option2events = venue_option2events

    def update(self, gamedata):
        self.__init__(gamedata._map, gamedata._venues)



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
    return GameData(game_map, venues)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = configparser.RawConfigParser()
    cfg.read(args.cfg)

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    gamedata = load_gamedata(cfg.get("auth", "credentials"), cfg.get("gamedata", "spreadsheet_id"))
