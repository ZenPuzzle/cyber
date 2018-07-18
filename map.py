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
            assert len(row) >= 5
            dir_id = DIR2DIR_ID[row[0]]
            to_id = row[2]
            multiplier = float(row[3])
            journey_descr = row[4]
            arrow = row[5] if len(row) >= 6 else None
            extra_button_markup = row[6] if len(row) >= 7 else None
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

    @staticmethod
    def parse_from_worksheet(worksheet):
        name = worksheet.get("{urn:schemas-microsoft-com:office:spreadsheet}Name", XML_NS)
        name = name.encode("utf8")
        try:
            int(name)
        except:
            return
        table = worksheet.find("xls:Table", XML_NS)
        rows = table.findall("xls:Row", XML_NS)
        first_row = get_cell_data(rows[0])
        if first_row is None or len(first_row) == 0:
            return
        first_cell = first_row[0]
        if first_cell is None:
            logging.warning("EMPTY_FIRST_ROW\t{}".format(name))
            return
        if first_cell.text != u"глобальная карта":
            logging.warning("BAD_FIRST_ROW\t{}".format(name))
            return
        descr = get_cell_data(rows[1])[0].text
        assert descr
        size = float(get_cell_data(rows[2])[1].text)
        research_rate = float(get_cell_data(rows[2])[3].text)
        x = float(get_cell_data(rows[3])[1].text)
        y = float(get_cell_data(rows[3])[3].text)

        adjacent = dict()
        for row_index in range(6, 16):
            cells = get_cell_data(rows[row_index])
            if len(cells) != 5:
                continue
            dir_id = DIR2DIR_ID[cells[0].text]
            to_id = cells[2].text
            try:
                multiplier = float(cells[3].text)
            except:
                logging.warning("BAD_MULTIPLIER\t{}\t{}".format(name,
                                cells[3].text.encode("utf8")))
                multiplier = 1
            journey_descr = cells[4].text
            adjacent[dir_id] = Transition(to_id, journey_descr, multiplier)

        objects, events = list(), list()
        sum_object_prob, sum_event_prob = 0, 0
        for row_index in range(17, len(rows)):
            cells = get_cell_data(rows[row_index])
            if cells[0] is None:
                continue
            object_name = cells[0].text
            if object_name:
                object_prob = float(cells[1].text)
                sum_object_prob += object_prob
                objects.append((sum_object_prob, object_name))
            event_name = cells[2 if len(cells) == 4 else 0].text
            if event_name:
                event_prob = float(cells[3 if len(cells) == 4 else 1].text)
                sum_event_prob += event_prob
                events.append((sum_event_prob, event_name))

        return Location(name, descr, size, research_rate, Position(x, y), adjacent, objects, events)


def parse_gamedata(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    print(root.tag)
    game_map = dict()
    for worksheet in root.findall("xls:Worksheet", XML_NS):
        location = Location.parse_from_worksheet(worksheet)
        if location is not None:
            assert location._id not in game_map
            game_map[location._id] = location
    logging.info("loaded {} locations: {}".format(len(game_map),
                 ", ".join(sorted(list(game_map.iterkeys())))))
    return game_map


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
