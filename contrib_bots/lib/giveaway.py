# See readme.md for instructions on running this code.
import time
import threading
import random

class GiveawayHandler(object):
    '''
    This plugin allows for "giveaways" to be run within a
    zulip stream. The bot will look for any message starting
    with "@giveaway" followed by a command (either init, enter,
    exit or cancel) followed by a time in seconds for the giveaway
    to run for. Full syntax is shown below:
    @giveaway command giveaway_name giveaway_time

    Possible commands:
    init - initialise a giveaway (only one can be running at a time)
    enter - enter a giveaway (a giveaway must be running to use this command)
    exit - leave a giveaway (must be partaking in an active giveaway for this
    command to work
    cancel - cancel a giveaway (can only be run by the person who first 
    initialised the giveaway

    This plugin was created by Daniel O'Brien
    as part of Google Code-In 2016-2017
    '''
    def __init__(self):
        self.giveawayArray = [] 
        self.giveawayOn = False
        self.giveawayName = ""
        self.giveawayTime = 0
        self.giveawayCreator = ""
        self.giveawayStartTime = 0
        self.giveawayGroup = ""
        self.giveawaySubject = ""
        self.giveawayClient = ""
        self.giveawayTimeMins = 0
        self.giveawayStage = 0
        self.one_minute_warning = False
        self.giveawayWinner = ""
        self.winnerContactDetails = []
        self.winnerIndex = 0

    def time_update(self, new_content):
            if self.giveawayOn == True:
                self.giveawayClient.send_message(dict(
                    type='stream',
                    to=self.giveawayStream,
                    subject=self.giveawaySubject,
                    content=new_content,
                ))
                threading.Timer(6.0, self.check_time).start()

    def check_time(self):
        if time.time() > (self.giveawayStartTime+self.giveawayTime):
            print("Giveaway ended")
            try:
                self.giveawayWinner = random.choice(self.giveawayArray)
                self.winnerIndex = self.giveawayArray.index(self.giveawayWinner)
                new_content = 'The giveaway has now ended... The winner is... %s!' % (self.giveawayWinner)
                direct_content = 'Congratulations!, you recently partook in the giveaway called %s and won! Please contact %s on details as to how to claim your prize.' % (self.giveawayName, self.giveawayCreator,)
                self.giveawayClient.send_message(dict(
                    type='private',
                    to=self.winnerContactDetails[self.winnerIndex],
                    content=direct_content,
                ))

            except:
                new_content = 'Giveaway ended: No one entered the giveaway :('
            if self.giveawayOn == True:
                self.giveawayOn = False
                self.giveawayClient.send_message(dict(
                    type='stream',
                    to=self.giveawayStream,
                    subject=self.giveawaySubject,
                    content=new_content,
                ))
            
        elif time.time() > (self.giveawayStartTime+(self.giveawayTime/4)) and self.giveawayStage < 1: #1/4 Time elapsed
            new_content = '1/4 of giveaway time elapsed, %s minutes remaining' % (str((self.giveawayTimeMins/4)*3))
            self.time_update(new_content)
            self.giveawayStage = self.giveawayStage + 1
        elif time.time() > (self.giveawayStartTime+(self.giveawayTime/2)) and self.giveawayStage < 2:
            new_content = '1/2 of giveaway time elapsed, %s minutes remaining' % (str(self.giveawayTimeMins/2))
            self.time_update(new_content)
            self.giveawayStage = self.giveawayStage + 1
        elif time.time() > (self.giveawayStartTime+((self.giveawayTime/4)*3)) and self.giveawayStage < 3:
            new_content = '3/4 of giveaway time elapsed, %s minutes remaining' % (str((self.giveawayTimeMins/4)*1))
            self.time_update(new_content)
            self.giveawayStage = self.giveawayStage + 1
        elif time.time() > ((self.giveawayStartTime+self.giveawayTime)-60) and self.giveawayTimeMins > 1.9 and self.one_minute_warning == False:
            new_content = 'Giveaway ends in 1 minute'
            self.time_update(new_content)
            self.one_minute_warning = True

        else:
            threading.Timer(6.0, self.check_time).start() #More efficient to check every 6 seconds instead of 1.

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
                - init: initialise a giveaway
                - enter: enter a giveaway (only works if a
                giveaway is already running_
                - exit: exit
                - cancel
            

            This plugin was created by Daniel O'Brien
            as part of Google Code-In 2016-2017
            '''

    def triage_message(self, message, client):
        # return True if we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting links
        # for own links!
        if message['display_recipient'] == 'giveawayer':
            return False
        is_giveaway = original_content.startswith('@giveaway')

        return is_giveaway
    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        if original_content.split(" ")[1] == "init":
            print("Giveaway: init")
            if self.giveawayOn == False:
                print("Giveaway: No giveaway currently running")
                try:
                    self.giveawayName = original_content.split(" ")[2]
                    self.giveawayCreator = original_sender
                    print("Giveaway: Creator -", self.giveawayCreator)
                    try:
                        self.giveawayTimeMins = round(float(original_content.split(" ")[3]), 1)
                        if self.giveawayTimeMins > 100: #Giveaway time must be less than 100 mins to avoid stack overflow. However, limit can be increased within python with the command sys.setrecursionlimit(NewLimit), default is 1000
                            new_content = 'Error: Giveaway time must be less than or equal to 100 mins'
                        else:
                            self.giveawayTime = self.giveawayTimeMins * 60
                            new_content = '%s has initiated a giveaway called %s for %s minutes' % (message['sender_full_name'],self.giveawayName, self.giveawayTimeMins)
                            self.giveawayOn = True
                            self.giveawayStartTime = time.time()
                            self.giveawayStream = message['display_recipient']
                            self.giveawaySubject = message['subject']
                            self.giveawayClient = client
                            self.giveawayStage = 0
                            self.one_minute_warning = False
                            self.check_time()
                    except:
                        new_content = 'Error: please enter a giveaway time (minutes)'
                except:
                    new_content = 'Error: Please enter a giveaway name'
            else:
                new_content = 'Error: Giveaway already running. Cancel using @giveaway cancel'

        elif original_content.split(" ")[1] == "enter":
            print("Giveaway enter")
            if self.giveawayOn == True:
                if message['sender_full_name'] not in self.giveawayArray and original_sender != self.giveawayCreator:
                    self.giveawayArray.append(message['sender_full_name'])
                    self.winnerContactDetails.append(original_sender)
                    new_content = '%s has entered the giveaway' % (message['sender_full_name'])
                elif original_sender in self.giveawayArray:
                    new_content = 'Error: You are already entered in this giveaway'
                else:
                    new_content = 'Error: You cannot participate in a giveaway that you created'
            else:
                new_content = 'Error: No giveaway currently running'
        elif original_content.split(" ")[1] == "exit":
            print("Giveaway exit")
            if original_sender in self.giveawayArray:
                self.giveawayArray.remove(original_sender)
                new_content = '%s has left the giveaway' % (original_sender,)
            else:
                new_content = 'Error: You are not currently participating in a giveaway'
        elif original_content.split(" ")[1] == "cancel":
            print("Giveaway cancel")
            if self.giveawayOn == True:
                if original_sender == self.giveawayCreator:
                    new_content = 'Giveaway cancelled'
                    self.giveawayOn = False
                else:
                    new_content = 'Error: Giveaway can only be cancelled by its creator (%s)' % (giveawayCreator)
        else:
            new_content = 'Error: Possible commands are "init", "enter", "exit" and "cancel"'

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content,
        ))

handler_class = GiveawayHandler


