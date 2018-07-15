#!/usr/bin/env python
#coding: utf8
from __future__ import print_function
from xml.etree import ElementTree as ET

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

    def __init__(self, to_id, descr, multiplier):
        self._to_id = to_id
        self._descr = descr
        self._multiplier = multiplier


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
    def parse_from_worksheet(worksheet):
        name = worksheet.get("{urn:schemas-microsoft-com:office:spreadsheet}Name", XML_NS)
        print(name)
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
            print(name, "empty first row")
            return
        if first_cell.text != u"глобальная карта":
            print(name, "bad first row data")
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
            dir_id = DIR2DIR_ID[cells[0].text]
            to_id = cells[2].text
            try:
                multiplier = float(cells[3].text)
            except:
                print("BAD MULTIPLIER, assuming 1", cells[3].text)
                multiplier = 1
            if len(cells) > 4:
                descr = cells[4].text
            else:
                descr = ""
            adjacent[dir_id] = Transition(to_id, descr, multiplier)

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
    print("read", len(game_map), "locations:", ", ".join(sorted(list(game_map.iterkeys()))))
    return game_map

if __name__ == "__main__":
    parse_gamedata("gamedata.xml")
