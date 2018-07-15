#!/usr/bin/env bash
PID=`ps x | grep run.py | grep python | awk '{print $1}'`
if [[ -n $PID ]]; then
    kill $PID
fi
nohup python run.py config.ini &
