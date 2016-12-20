class PollHandler(object):
    '''
    This plugin allows users to create polls.
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
        @poll init <question>: <option1>, <option2>, <option3>
        A valid poll must use a colon (:) to divide question from answers.
        Answers must be seperate by coma (,).

        @poll <option1>
        Question will be infered by scanning channel for last poll with
        valid answer.

        @poll result poll title
        Returns a formatted version of the poll.

        @poll help
        Returns usage for polling bot.

        >>> @poll init what's the best ice cream flavour: vanilla, chocolate
        <<< Question successfully created! Answer away
        >>> @poll vanilla
        <<< vanilla has 1 vote
        >>> @poll result what's the best ice cream flavour
        <<< what's the best ice cream flavour:
        <<< vanilla: 1
        <<< chocolate: 0
        '''

    # Returns True if message is respondable
    def triage_message(self, message):
        original_content = message['content'].lower()

        if message['display_recipient'] == 'poll':
            return False

        if original_content.startswith('@poll'):
            return True
        else:
            return False

    def handle_message(self, message, client, state_handler):
        original_content = message['content'].lower()

        if original_content.startswith('@poll init'):
            split = original_content.split(': ', 1)
            if len(split) == 2:
                question = split[0].split(' ', 2)[-1]
                answers = split[1].split(', ')
                if question in self.polls:
                    new_content = "Question already exists."
                else:
                    self.polls[question] = dict((elem, 0) for elem in answers)
                    self.streams[message['subject']] = question
                    new_content = "Question successfully created! Answer away"
            else:
                new_content = "Question was incorrectly formatted. See @poll help for usage"
        elif original_content.startswith('@poll result'):
            split = original_content.split(' ', 2)
            if len(split) == 3:
                question = split[-1]
                if question in self.polls:
                    new_content = question + ': \n' + ''.join(
                        ((str(key) + ': ' + str(value) + '\n')
                        for key, value in self.polls[question].iteritems())
                    )
                else:
                    new_content = "No such poll exists. Possibly check spelling."
        elif original_content.startswith('@poll help'):
            new_content = self.usage()
        elif original_content.startswith('@poll'):
            if not message['subject'] in self.streams:
                new_content = "There doesn't appear to be a poll in this stream."
            elif not original_content.split(' ', 2)[-1] in self.polls[self.streams[message['subject']]]:
                new_content = "The current question doesn't appear to have that option. Possibly check spelling."
            else:
                question = self.streams[message['subject']]
                answer = original_content.split(' ', 2)[-1]
                self.polls[question][answer] += 1
                new_content = answer + ' has ' + str(self.polls[question][answer]) + ' vote'

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content,
        ))

handler_class = PollHandler
