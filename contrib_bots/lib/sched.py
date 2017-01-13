# pip install schedule is necessary
import schedule
import time
import json
import threading
import os
import uuid
from random import randint

config = os.path.expanduser('~/.sched')
with open(config) as data_file:
    wakeup = json.load(data_file)[0]

cache = os.path.expanduser('~/.cache/sched')
# Verify is hour format is valid
def is_time_format(format):
    try:
        time.strptime(format, '%H:%M')
        return True
    except ValueError:
        return False

# For every task we want to schedule we define a job that have a random unique id  to cancel the task.

def job(randomint, message, client):
    original_content = message['content']
    reduced_message_list = original_content.split()[3:]
    reduced_message_string = " ".join(reduced_message_list)
    if reduced_message_string:
        if reduced_message_string.split()[0] == "at":
            reduced_message_string = reduced_message_string.split()[2:]
            reduced_message_string = " ".join(reduced_message_string)

    events = dict(
        type='stream',
        to='alert',
        subject="All alerts",
        content=reduced_message_string+" "+randomint,
        )
    client.send_message(events)

def wait():
    while True:
       schedule.run_pending()
       time.sleep(1)

def send_message_once(client):
        events = dict(
            type='stream',
            to='alert',
            subject="All alerts",
            content="@recover 0",
        )
        client.send_message(events)
        return schedule.CancelJob

def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

class SchedHandler(object):
    def __init__(self, client):
        schedule.every(1).seconds.do(send_message_once, client)
        run_threaded(wait)

    '''
    This bot allows you to schedule daily alerts. It
    looks for messages starting with '@every' or '@cancel' or '@recover'.
    In this example, we write alerts at certain time intervals
    in a new stream called "alert,".
    '''

    def usage(self):
        return '''
            Users should preface messages with "@every" or '@cancel' or '@recover'.

            Before running this, make sure to create a stream
            called "alert" that your API user can send to.
            '''

    def triage_message(self, message):
        # return True if we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups.
        is_link = (original_content.startswith('@every') or
                   original_content.startswith('@cancel') or
                   original_content.startswith('@recover'))

        return is_link

    def handle_message(self, message, client, state_handler):

        original_content = message['content']
        uid = uuid.uuid4()
        uid_str = uid.urn[9:]
        key = dict(
            type='stream',
            to='alert',
            subject="All alerts",
            content=original_content+" "+uid_str,
            )

        # List needed to verify if time interval was valid.
        weekday = ["monday", "tuesday", "wednesday", "thursday",
                   "friday", "saturday", "sunday", "day"]

        weekdays = ["{}s".format(d) for d in weekday]

        intervals = ["hour", "hours", "minute", "minutes"]
        # Verify that @every command meets the syntax required for data indexing.
        # Doing that for @every x time.
        if len(original_content.split()) > 2:
            coefficient = original_content.split()[1]
            interval = original_content.split()[2]
            if (original_content.startswith('@every') and interval in intervals):
                with open(cache) as data_file:
                    data = json.load(data_file)
                if key not in data:
                    data.append(key)
                with open(cache, 'w') as data_file:
                    json.dump(data, data_file)
                int_coefficient = int(coefficient)
                if interval.endswith("s") == False:
                   interval = interval+"s"
                task = schedule.every(int_coefficient)
                task = getattr(task, interval)
                task.do(job, uid_str, message, client).tag(uid_str)
        # Doing that for @every x time at hour.
        if len(original_content.split()) > 4:
            timer = original_content.split()[4]
            if (original_content.startswith('@every') and coefficient.isdigit() and
                (interval in weekdays or interval in weekday)
                and is_time_format(timer)):
                with open(cache) as data_file:
                    data = json.load(data_file)
                if key not in data:
                    data.append(key)
                with open(cache, 'w') as data_file:
                    json.dump(data, data_file)
                int_coefficient = int(coefficient)
                if interval in weekdays:
                   interval = interval[:-1]
                task = schedule.every(int_coefficient)
                task = getattr(task, interval)
                task.at(timer).do(job, uid_str, message, client).tag(uid_str)

        # Cancel command will remove events from persistence list and from the current schedule.
        if original_content.startswith('@cancel'):
            id = original_content.split()[1]
            with open(cache) as data_file:
                data = json.load(data_file)
            updated_data = [x for x in data if id != dict(x)["content"].split()[-1]]
            with open(cache, 'w') as data_file:
                json.dump(updated_data, data_file)
            schedule.clear(id)
            client.send_message(dict(
                type='stream',
                to="alert",
                subject="All alerts",
                content="You successfully cancelled your task!"
            ))

        if original_content.startswith('@recover'):
            # Recover command needs to be run if the bot is stopped, it will re-schedule all tasks.
            with open(cache) as data_file:
                data = json.load(data_file)
                try:
                    i = int(original_content.split()[1])
                    if i < len(data):
                        content = data[i]["content"]
                        message["content"] = content
                        command = content.split()[0]
                        if command == "@every":
                            coefficient = int(content.split()[1])
                            interval = content.split()[2]
                            original_tag = content.split()[-1]
                            if (interval in weekdays or interval in weekday):
                                timer = content.split()[4]
                                # This if allows the bot to understand command with plurals intervals.
                                if interval in weekdays:
                                    interval = interval[:-1]
                                task = schedule.every(coefficient)
                                task = getattr(task, interval)
                                task.at(timer).do(job, '', message, client).tag(original_tag)
                            if interval in intervals:
                                if (coefficient < 2 and interval.endswith("s")):
                                    interval = interval[:-1]
                                if (coefficient > 1 and interval.endswith("s") == False):
                                    interval = interval+"s"
                                task = schedule.every(coefficient)
                                task = getattr(task, interval)
                                task.do(job, '', message, client).tag(original_tag)
                        client.send_message(dict(
                            type='stream',
                            to="alert",
                            subject="All alerts",
                            content="@recover" + " " + str(i+1)
                        ))
                except KeyError:
                    return "Recovered"

handler_class = SchedHandler

