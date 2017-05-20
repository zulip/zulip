import itertools

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

        # closed is a list of closed polls.
        self.closed = list()

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

        @poll close
        Closes voting for current poll.

        @poll result <question or "current" for current poll>
        Returns a formatted version of the poll.

        @poll help
        Returns usage for polling bot.

        >>> @poll init what's the best ice cream flavour: vanilla, chocolate
        <<< @**USER** created a poll!
        <<< Question: what's the best ice cream flavour
        <<< Option 1: Vanilla
        <<< Option 2: chocolate
        <<< You can answer this poll by writing `@poll <option>` in this stream.
        >>> @poll vanilla
        <<< vanilla has 1 vote
        >>> @poll close
        <<< Poll - what's the best ice cream flavour - is now closed.
        >>> @poll result
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

        if original_content.startswith('@poll help'):
            new_content = self.usage()
        elif original_content.startswith('@poll init'):
            split = original_content.split(': ', 1)
            if len(split) == 2:
                question = split[0].split(' ', 2)[-1]
                answers = split[1].split(', ')
                if question in self.polls:
                    new_content = "Question already exists."
                else:
                    self.polls[question] = dict((elem, 0) for elem in answers)
                    self.streams[message['subject']] = question
                    new_content = new_content = ("@**" + message['sender_full_name'] + "** Created a poll!" + '\n' +
                                                 "Question: " + question + "\n" +
                                                 ''.join(
                                                         (("Option " + str(answers.index(answer) + 1) + ": " + answer + "\n")
                                                         for answer in answers)) +
                                                 "\n" + "You can answer this poll by writing `@answer <option>` in this stream.")
            else:
                new_content = "Question was incorrectly formatted. See @poll help for usage"
        elif original_content.startswith('@poll result'):
            split = original_content.split(' ', 2)
            if len(split) == 3:
                question = split[-1]
            elif message['subject'] in self.streams:
                question = self.streams[message['subject']]

            if question is not None and question in self.polls:
                new_content = question + ': \n' + ''.join(
                                                          ((str(key) + ': ' + str(value) + '\n')
                                                          for key, value in self.polls[question].iteritems()))
            else:
                new_content = "No valid poll specified and no current poll was found."
        elif original_content.startswith('@poll list'):
            split = original_content.split(' ', 2)
            if len(split) == 2:
                count = 5
            elif len(split) == 3:
                count = int(split[-1])
            new_content = ''.join(
                                  ''.join(question + ":\n" + ''.join(((str(key) + ': ' + str(value) + '\n'))
                                  for key, value in poll.iteritems())
                                  for question, poll in itertools.islice(self.polls.iteritems(), count)))
        elif original_content.startswith('@poll close'):
            split = original_content.split(' ', 2)
            if len(split) == 2:
                if not message['subject'] in self.streams:
                    new_content = "There doesn't appear to be a poll in this stream."
                if self.streams[message['subject']] in self.closed:
                    new_content = "This poll has already been closed."
                else:
                    question = self.streams[message['subject']]
                    self.closed += question
                    new_content = "Poll - " + question + " - is not closed."
        elif original_content.startswith('@poll'):
            if not message['subject'] in self.streams:
                new_content = "There doesn't appear to be a poll in this stream."
            elif not original_content.split(' ', 2)[-1] in self.polls[self.streams[message['subject']]]:
                new_content = "The current question doesn't appear to have that option. Possibly check spelling."
            elif self.streams[message['subject']] in self.closed:
                new_content = "This poll has already been closed."
            else:
                question = self.streams[message['subject']]
                answer = original_content.split(' ', 2)[-1]
                self.polls[question][answer] += 1
                new_content = answer + ' has ' + str(self.polls[question][answer]) + ' vote'

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content or "internal error",
        ))

handler_class = PollHandler
