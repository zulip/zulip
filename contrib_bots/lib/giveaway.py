# See readme.md for instructions on running this code.
from __future__ import print_function
import time
import threading
import random
from past.utils import old_div

class GiveawayHandler(object):
    '''
    This plugin allows for "giveaways" to be run within a
    zulip stream. The bot will look for any message starting
    with "@giveaway" followed by a command (either init, enter,
    exit or cancel) followed by a time in seconds for the giveaway
    to run for. Full syntax is shown below:
    @giveaway command giveaway_name giveaway_time

    Possible commands:
    init - initialize a giveaway (only one can be running at a time)
    enter - enter a giveaway (a giveaway must be running to use this command)
    exit - leave a giveaway (must be partaking in an active giveaway for this
    command to work
    cancel - cancel a giveaway (can only be run by the person who first
    initialised the giveaway

    This plugin was created by Daniel O'Brien
    as part of Google Code-In 2016-2017
    '''
    def __init__(self):
        self.giveaway_array = []
        self.giveaway_on = False
        self.giveaway_name = ""
        self.giveaway_time = 0
        self.giveaway_creator = ""
        self.giveaway_start_time = 0
        self.giveaway_group = ""
        self.giveaway_subject = ""
        self.giveaway_client = ""
        self.giveaway_timeMins = 0
        self.giveaway_stage = 0
        self.one_minute_warning = False
        self.giveaway_winner = ""
        self.giveaway_winner_contact_address = []
        self.winner_index = 0
        self.all_warnings_fired = False

    def time_update(self, new_content):
        if self.giveaway_on:
            self.giveaway_client.send_message(dict(
                type='stream',
                to=self.giveawayStream,
                subject=self.giveaway_subject,
                content=new_content,
            ))
            threading.Timer(6.0, self.check_time).start()

    def time_warning(self):
        if self.giveaway_stage == 0:
            self.numerator = 1
            self.denominator = 4
        elif self.giveaway_stage == 1:
            self.numerator = 1
            self.denominator = 2
        elif self.giveaway_stage == 2:
            self.numerator = 3
            self.denominator = 4
        elif self.giveaway_stage == 0:
            self.all_warnings_fired = True
        if time.time() > ((self.giveaway_start_time + self.giveaway_time)-60):
            if self.giveaway_timeMins > 1.9 and not self.one_minute_warning:
                new_content = 'Giveaway ends in 1 minute'
                self.time_update(new_content)
                self.one_minute_warning = True
        elif time.time() > (self.giveaway_start_time + (old_div(self.giveaway_time, self.denominator)*self.numerator)):
            if not self.all_warnings_fired:
                new_content = ('{}/{} of giveaway time elapsed, {} minutes remaining'
                               .format(self.numerator, self.denominator, str((old_div(self.giveaway_timeMins, 4))*3)))
                self.time_update(new_content)
                self.giveaway_stage = self.giveaway_stage + 1

    def check_time(self):
        if time.time() > (self.giveaway_start_time + self.giveaway_time):
            print("Giveaway ended")
            try:
                self.giveaway_winner = random.choice(self.giveaway_array)
                self.winner_index = self.giveaway_array.index(self.giveaway_winner)
                new_content = 'The giveaway has now ended... The winner is... {}!'.format(self.giveaway_winner)
                direct_content = """Congratulations!, you recently partook in the giveaway called {} and won!
                Please contact {} on details as to how to claim your prize.""".format(self.giveaway_name, self.giveaway_creator,)
                self.giveaway_client.send_message(dict(
                    type='private',
                    to=self.giveaway_winner_contact_address[self.winner_index],
                    content=direct_content,
                ))
            except:
                new_content = 'Giveaway ended: No one entered the giveaway :('
            if self.giveaway_on:
                self.giveaway_on = False
                self.giveaway_client.send_message(dict(
                    type='stream',
                    to=self.giveawayStream,
                    subject=self.giveaway_subject,
                    content=new_content,
                ))
        self.time_warning()
        threading.Timer(6.0, self.check_time).start() # More efficient to check every 6 seconds instead of 1.

    def usage(self):
        return '''
            This plugin will allow for users to create
            giveaways which people can enter. After a set
            period of time has passed, a random person will
            be chosen from the list of random people whom
            entered the giveaway.

            Syntax:
            @giveaway command giveaway_name giveaway_time

            Command:
                - init: initialize a giveaway
                - enter: enter a giveaway (only works if a
                giveaway is already running)
                - exit: exit
                - cancel

            This plugin was created by Daniel O'Brien
            as part of Google Code-In 2016-2017
            '''

    def triage_message(self, message, client):
        # return True if we want to (possibly) response to this message

        original_content = message['content']
        if message['display_recipient'] == 'giveawayer':
            return False
        return original_content.startswith('@giveaway')

    def handle_message(self, message, client, state_handler):

        original_content = message['content']
        original_sender = message['sender_email']
        if original_content.split(" ")[1] == "init":
            print("Giveaway: init")
            if not self.giveaway_on:
                print("Giveaway: No giveaway currently running")
                try:
                    self.giveaway_name = original_content.split(" ")[2]
                    self.giveaway_creator = original_sender
                    try:
                        self.giveaway_timeMins = round(float(original_content.split(" ")[3]), 1)
                        if self.giveaway_timeMins > 100:
                            # Giveaway time must be less than 100 mins to avoid stack overflow.
                            # However, limit can be increased within python with the command
                            # sys.setrecursionlimit(NewLimit), default is 1000
                            new_content = 'Error: Giveaway time must be less than or equal to 100 mins'
                        else:
                            self.giveaway_time = self.giveaway_timeMins * 60
                            new_content = ("""{} has initiated a giveaway called {} for {} minutes"""
                                           .format(message['sender_full_name'], self.giveaway_name, self.giveaway_timeMins))
                            self.giveaway_on = True
                            self.giveaway_start_time = time.time()
                            self.giveawayStream = message['display_recipient']
                            self.giveaway_subject = message['subject']
                            self.giveaway_client = client
                            self.giveaway_stage = 0
                            self.one_minute_warning = False
                            self.check_time()
                    except:
                        new_content = 'Error: please enter a giveaway time (minutes)'
                except:
                    new_content = 'Error: Please enter a giveaway name'
            else:
                new_content = """Error: Giveaway already running in the {} stream. If you
                                 created the giveaway, you can cancel it using @giveaway cancel.
                                 If not, please contact the creator of the giveaway and ask them
                                 to cancel it for you."""

        elif original_content.split(" ")[1] == "enter":
            print("Giveaway enter")
            if self.giveaway_on:
                if message['sender_full_name'] not in self.giveaway_array and original_sender != self.giveaway_creator:
                    self.giveaway_array.append(message['sender_full_name'])
                    self.giveaway_winner_contact_address.append(original_sender)
                    new_content = '{} has entered the giveaway'.format(message['sender_full_name'])
                elif original_sender in self.giveaway_array:
                    new_content = 'Error: You are already entered in this giveaway'
                else:
                    new_content = 'Error: You cannot participate in a giveaway that you created'
            else:
                new_content = 'Error: No giveaway currently running'
        elif original_content.split(" ")[1] == "exit":
            print("Giveaway exit")
            if original_sender in self.giveaway_array:
                self.giveaway_array.remove(original_sender)
                new_content = '{} has left the giveaway'.format(original_sender,)
            else:
                new_content = 'Error: You are not currently participating in a giveaway'
        elif original_content.split(" ")[1] == "cancel":
            print("Giveaway cancel")
            if self.giveaway_on:
                if original_sender == self.giveaway_creator:
                    new_content = 'Giveaway cancelled'
                    self.giveaway_on = False
                else:
                    new_content = 'Error: Giveaway can only be cancelled by its creator ({})'.format(self.giveaway_creator)
        else:
            new_content = 'Error: Possible commands are "init", "enter", "exit" and "cancel"'

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content,
        ))

handler_class = GiveawayHandler
