#!/usr/bin/env python
from __future__ import print_function
import argparse
import ConfigParser

import telegram


def run_main_loop(token):
    bot = telegram.Bot(token=token)
    user = bot.get_me()
    print(user.to_json())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg")
    args = parser.parse_args()

    cfg = ConfigParser.RawConfigParser()
    cfg.read(args.cfg)

    run_main_loop(cfg.get("auth", "token"))


if __name__ == "__main__":
    main()
