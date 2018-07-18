#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
from xml.etree import ElementTree as ET
import logging
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import json
import argparse
import ConfigParser as configparser

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

    def __init__(self, id, descr, size, research_rate, pos, adjacent, objects, events):
        self._id = id
        self._descr = descr
        self._size = size
        self._research_rate = research_rate
        self._pos = pos
        self._adjacent = adjacent
        self._objects = objects
        self._events = events

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
        objects = list()
        while row_index < len(rows) and rows[row_index][0] != u"случайные ивенты":
            row = rows[row_index]
            if len(row) >= 3:
                object_name, prob, object_descr = row[:3]
                assert prob.endswith("%")
                prob = int(prob[:-1]) * 0.1
                objects.append((prob, object_name, object_descr))
            row_index += 1

        events = list()
        if row_index < len(rows):
            row_index += 1
            while row_index < len(rows):
                row = rows[row_index]
                if len(row) >= 2:
                    event_name, prob = row[:2]
                    assert prob.endswith("%")
                    prob = int(prob[:-1]) * 0.1
                    events.append((prob, event_name))
                row_index += 1
        return Location("", descr, size, research_rate, Position(x, y), adjacent, objects, events)


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
    logging.info("loaded {} locations: {}".format(len(game_map),
                 ", ".join(sorted(list(game_map.iterkeys())))))
    return game_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = configparser.RawConfigParser()
    cfg.read(args.cfg)

    game_map = load_gamedata(cfg.get("auth", "credentials"), cfg.get("gamedata", "spreadsheet_id"))
