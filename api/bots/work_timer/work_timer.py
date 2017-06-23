# See readme.md for instructions on running this code.
from time import time
from threading import Timer

class WorkTimerHandler(object):
    def usage(self):
        return '''
        This productivity bot lets you set timers to schedule work cycles.
        Start a new timer with the following syntax:
        work - set a work timer for the default 25 minutes
        work on [task] - set a work timer, and specify what you're working on
        work for [time] - set a work timer for a custom number of minutes
        work on [task] for [time] - combines the two above

        When you have a task running, you can call **status** to check how much
        time you have left. You'll be notified when your timer runs out.
        '''

    def handle_message(self, message, bot_handler, state_handler, event_timer):
        state = state_handler.get_state() or {}
        req = message['content'].lower()
        user = message['sender_email']
        content = 'I didn\'t understand that. Say "help" for usage information.'
        malformed = ''
        if 'work' in req:
            task = ''
            task_time = 25
            malformed = ''
            if 'for' in req:
                req,_,time_input = req.rpartition('for')
                time_input = time_input.strip().split(' ')
                if len(time_input) > 2:
                    malformed = '**Error:** Please format as "work on [task] for [minutes]".'
                try:
                    task_time = int(time_input[0])
                except ValueError:
                    malformed = '**Error:** Invalid time specified (please use an integer).'
            content = 'for {} minutes.'.format(task_time)
            if 'on' in req:
                task = req.partition('on')[2].strip()
                content = 'on {} '.format(task) + content
            content = 'Ok, setting a timer to work ' + content
            if not malformed:
                if not user in state:
                    state[user] = {}
                task_time *= 60
                state[user]['time'] = time() + task_time
                state[user]['task'] = task

                task_func = self.build_task_wrapper(user, task, bot_handler)
                event_timer.schedule(task_func, task_time)
        elif 'status' in req:
            if user not in state or state[user]['time'] - time() < 0:
                content = 'You have no active timers.'
            else:
                mins = int(state[user]['time'] - time() + 30)/60
                time_str = "You have about {} minutes left.".format(mins)
                if mins == 1:
                    time_str = "You have about 1 minute left."
                elif mins == 0:
                    time_str = "You have under a minute left."
                if state[user]['task']:
                    content = 'You\'re supposed to be working on {}. '.format(state[user]['task'])
                else:
                    content = 'You\'re supposed to be working. '
                content += time_str
        elif 'help' in req:
            content = self.usage()

        if malformed:
            content = malformed
        state_handler.set_state(state)
        bot_handler.send_reply(message, content)

    def build_task_wrapper(self, user, task, bot_handler):
        return lambda: self.on_task_finish(user, task, bot_handler)

    def on_task_finish(self, user, task, bot_handler):
        message = '''Your timer has ended! You've been working on {}.
        Give a new "work" command or take a break.'''.format(task)

        bot_handler.send_message(dict(
            type='private',
            to=user,
            content=message,
        ))

handler_class = WorkTimerHandler
