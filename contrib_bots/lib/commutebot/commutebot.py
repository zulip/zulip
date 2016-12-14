import requests

class CommuteHandler(object):
    '''
    This plugin provides information regarding commuting from an origin to a destination, providing
    a multitude of information. It looks for messages starting with '@commute'.
    '''

    def usage(self):
        return '''
            This plugin will allow briefings of estimated travel times,
              distances and fare information for transit travel. It can vary outputs
              depending on traffic conditions, departure and arrival times as well as
              user preferences (toll avoidance, preference for bus travel, etc.).
            It looks for messages starting with '@commute'.

            Users should input an origin, destination and a mode of transport.
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        if message['display_recipient'] == 'commute':
            return False
        is_follow_up = (original_content.startswith('@commute') or
                        original_content.startswith('@commute'))

        return is_follow_up

    # allows bot to send info via private message or same stream depending on
    # user input
    def send_info(self, message, letter, client):
        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=letter,
            ))
        else:
            client.send_message(dict(
                type='stream',
                subject=message['subject'],
                to=message['display_recipient'],
                content=letter,
            ))

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        content_list = original_content.split()

        if "help" in content_list:
            help_info='''
    Obligatory Inputs:
        Origin (origin=New York,NY,USA)
        Destination (destinations=Chicago,IL,USA)
        Mode Of Transport (Accepted inputs:driving, walking, bicycling, transit) (mode=driving)
    Optional Inputs:
        Units (Metric or imperial) (units=metric)
        Restrictions (Accepted inputs:tolls, highways, ferries, indoor) (avoid=tolls)
        Departure Time (Seconds After Midnight January 1, 1970 UTC) (departure_time=now)
        Arrival Time (Seconds After Midnight January 1, 1970 UTC) (arrival_time=732283981023)
        Language (Available languages available here: https://developers.google.com/maps/faq#languagesupport) (lan=fr)

    Sample request:
        @commute origin=Chicago,IL,USA destination=New+York,NY,USA mode=driving language=fr

    Please note:
        Fare information can be derived, though is solely dependent on the
         availability of the information released by public transport operators
        Duration in traffic can only be derived if a departure time is set.
        If a location has spaces in its name, please use a + symbol in the place of the space/s
        A departure time and a arrival time can not be inputted at the same time
        To add more than 1 input for a category,
        eg. more than 1 destinations, use |, eg. destinations=Trump+Tower|The+White+House
        No spaces within addresses.


                            '''
            self.send_info(message, help_info, client)
        else:
            para = {}
            # converts input parameters for api into a dictionary structure for more aethestic coding
            for item in content_list:
                # enables key value pair
                org = item.split('=')

                # ensures that invalid inputs are not entered into url request
                if len(org) != 2:
                    continue

                key = org[0]
                value = org[1]
                para.update({key:value})

            #adds API Authentication Key to url request
            para.update({'key':'AIzaSyCGrx2FIMDVvfjYGgIjN9ocKyd5cfOiH-M'})

            # sends url api request and converts response into json format
            r = requests.get('https://maps.googleapis.com/maps/api/distancematrix/json', params=para)
            rjson = r.json()

            # determines if commute information will be outputted
            again_message = True

            # determines if user has valid inputs
            try:
                test1 = (rjson["rows"][0]["elements"][0]["status"] == "NOT_FOUND")
                test2 = (rjson["status"] == "INVALID_REQUEST")

                yes_results = (rjson["rows"][0]["elements"][0]["status"] == "ZERO_RESULTS")

                if yes_results:
                    self.send_info(message, "Zero results\nIf stuck, try '@commute help'", client)
                    again_message = False

                elif test1 or test2:
                    raise IndexError
            except IndexError:
                self.send_info(message, "Invalid input, please input as per instructions.\nIf stuck, try '@commute help'", client)
                again_message = False

            if again_message:
                # origin and destination strings
                begin = 'From: ' + rjson["destination_addresses"][0]
                end = 'To: ' + rjson["origin_addresses"][0]
                distance = 'Distance: ' + rjson["rows"][0]["elements"][0]["distance"]["text"]
                duration = 'Duration: ' + rjson["rows"][0]["elements"][0]["duration"]["text"]
                output = begin + '\n' + end + '\n' + distance

                # determines if fare information is available
                try:
                    fare =  'Fare: ' + rjson["rows"][0]["elements"][0]["fare"]["currency"] + rjson["rows"][0]["elements"][0]["fare"]["text"]
                    output += '\n' + fare
                except (KeyError, IndexError):
                    print('')

                # determines if traffic duration information is available
                try:
                    traf_dur = 'Duration in traffic: ' + rjson["rows"][0]["elements"][0]["duration_in_traffic"]["text"]
                    output += '\n' + traf_dur
                except (KeyError, IndexError):
                    output += '\n' + duration

                # bot sends commute information to user
                self.send_info(message, output, client)
handler_class = CommuteHandler
