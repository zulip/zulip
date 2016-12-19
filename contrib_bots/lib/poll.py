

class PollHandler(object):
    '''
    This plugin facilitates polling.
    '''

    def __init__(self):
        # polls is a dict of dict. First dict corresponds to poll title,
        # second refers to answers in poll
        self.polls = dict()

        # streams is a convenience object that keeps track of the latest
        # question for each stream.
        self.streams = dict()

    def usage(self):
        return '''
        This plugin facilitates polling.

        Commands:
        @question poll title: option 1, option 2, option 3
        A valid poll must use a colon (:) to devide question from answers.
        Answers must be seperate by coma (,).

        @answer option 1
        Question will be infered by scanning channel for last poll with
        valid answer.

        @result poll title
        Returns a formatted version of the poll.

        >> @question what's the best ice cream flavour: vanilla, chocolate
        << Question successfully created! Answer away
        >> @answer vanilla
        << vanilla has 1 vote
        >> @result what's the best ice cream flavour
        << what's the best ice cream flavour:
        << vanilla: 1
        << chocolate: 0
        '''

    # Returns True if message is respondable
    def triage_message(self, message):
        original_content = message['content'].lower()

        if message['display_recipient'] == 'poll':
            return False

        if original_content.startswith('@question'):
            return True
        elif original_content.startswith('@answer'):
            return True
        elif original_content.startswith('@result'):
            return True
        else:
            return False

    def handle_message(self, message, client, state_handler):
        original_content = message['content'].lower()
        original_sender = message['sender_email']

        if original_content.startswith('@question'):
            split = original_content.split(': ', 1)
            if len(split) == 2:
                question = split[0].split(' ', 1)[1]
                answers = split[1].split(', ')
                if question in self.polls:
                    new_content = "Question already exists."
                else:
                    self.polls[question] = dict((elem, 0) for elem in answers)
                    self.streams[message['subject']] = question
                    new_content = "Question successfully created! Answer away"
            else:
                new_content = "Question was incorrectly formatted. Check doc for usage"
        elif original_content.startswith('@answer'):
            if not message['subject'] in self.streams:
                new_content = "There doesn't appear to be a poll in this stream."
            elif not original_content.split(' ', 1)[1] in self.polls[self.streams[message['subject']]]:
                new_content = "The current question doesn't appear to have that option. Possibly check spelling."
            else:
                question = self.streams[message['subject']]
                answer = original_content.split(' ', 1)[1]
                self.polls[question][answer] += 1
                new_content = answer + ' has ' + str(self.polls[question][answer]) + ' vote'
        elif original_content.startswith('@result'):
            split = original_content.split(' ', 1)
            if len(split) == 2:
                question = split[1]
                if question in self.polls:
                    new_content = question + ': \n' + ''.join(
                        ((str(key) + ': ' + str(value) + '\n')
                        for key, value in self.polls[question].iteritems())
                    )
                else:
                    new_content = "No such poll exists. Possibly check spelling."

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content,
        ))

handler_class = PollHandler
