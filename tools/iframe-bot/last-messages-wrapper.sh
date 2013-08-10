#!/bin/sh

## For some reason, this doesn't work with a bot user.
#BOT_EMAIL=bot1@customer3.invalid
#API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BOT_EMAIL=wdaher@gmail.com
API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
STREAMS="event1 hongkong etc"
COUNT=50

mkdir -p output
while true; do

if python show-last-messages --api-key=$API_KEY --user=$BOT_EMAIL --streams="$STREAMS" --count=$COUNT; then
    echo "[`date`] Success";
    mv output-candidate.html output/zulip.html
    touch output/zulip.html
else
    echo "[`date`] FAILURE";
fi

sleep 30;

done
