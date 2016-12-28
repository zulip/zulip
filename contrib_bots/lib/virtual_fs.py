# See readme.md for instructions on running this code.

import re
import os

class VirtualFsHandler(object):
    def usage(self):
        return get_help()

    def triage_message(self, message, client):
        # return True iff we want to (possibly) response to this message
        if message['type'] != 'stream':
            return False

        original_content = message['content']
        return original_content.startswith('fs ')

    def handle_message(self, message, client, state_handler):
        assert self.triage_message(message, client)

        original_content = message['content']
        command = original_content[len('fs '):]
        stream = message['display_recipient']
        topic = message['subject']

        state = state_handler.get_state()
        if state is None:
            state = {}

        if stream not in state:
            state[stream] = fs_new()

        fs = state[stream]
        fs, msg = fs_command(fs, command)
        state[stream] = fs
        state_handler.set_state(state)

        client.send_message(dict(
            type='stream',
            to=stream,
            subject=topic,
            content=msg,
        ))


def get_help():
    return '''
The "fs" commands implement a virtual file system for a stream.
The locations of text are persisted for the lifetime of the bot
running, and if you rename a stream, you will lose the info.

Example commands:

```
fs mkdir: create a directory
fs ls: list a directory
fs write: write text
fs read: read text
fs rm: remove a file
```

Use commands like `fs help write` for more details on specific
commands.
'''

def test():
    fs = fs_new()
    assert is_directory(fs, '/')

    for cmd, expected_response in sample_conversation():
        fs, msg = fs_command(fs, cmd)
        if msg != expected_response:
            raise AssertionError('''
                cmd: %s
                expected: %s
                but got : %s
                ''' % (cmd, expected_response, msg))

def sample_conversation():
    return [
        ('write /foo contents of /foo', 'file written'),
        ('read /foo', 'contents of /foo'),
        ('write /bar Contents: bar bar', 'file written'),
        ('read /bar', 'Contents: bar bar'),
        ('write /bar invalid', 'ERROR: file already exists'),
        ('rm /bar', 'removed'),
        ('rm /bar', 'ERROR: file does not exist'),
        ('write /bar new bar', 'file written'),
        ('read /bar', 'new bar'),
        ('write /yo/invalid whatever', 'ERROR: /yo is not a directory'),
        ('mkdir /yo', 'directory created'),
        ('ls /yo', 'WARNING: directory is empty'),
        ('read /yo/nada', 'ERROR: file does not exist'),
        ('write /yo whatever', 'ERROR: file already exists'),
        ('write /yo/apple red', 'file written'),
        ('read /yo/apple', 'red'),
        ('mkdir /yo/apple', 'ERROR: file already exists'),
        ('ls /invalid', 'ERROR: file does not exist'),
        ('ls /foo', 'ERROR: /foo is not a directory'),
        ('ls /', '* /bar\n* /foo\n* /yo'),
        ('invalid command', 'ERROR: unrecognized command'),
        ('write', 'ERROR: syntax: write <path> <some_text>'),
        ('help', get_help()),
        ('help ls', 'syntax: ls <path>'),
        ('help invalid_command', get_help()),
    ]

REGEXES = dict(
    command='(ls|mkdir|read|rm|write)',
    path='(\S+)',
    some_text='(.+)',
)

def get_commands():
    return {
        'help': (fs_help, ['command']),
        'ls': (fs_ls, ['path']),
        'mkdir': (fs_mkdir, ['path']),
        'read': (fs_read, ['path']),
        'rm': (fs_rm, ['path']),
        'write': (fs_write, ['path', 'some_text']),
    }

def fs_command(fs, cmd):
    if cmd.strip() == 'help':
        return fs, get_help()

    cmd_name = cmd.split()[0]
    commands = get_commands()
    if cmd_name not in commands:
        return fs, 'ERROR: unrecognized command'

    f, arg_names = commands[cmd_name]
    partial_regexes = [cmd_name] + [REGEXES[a] for a in arg_names]
    regex = ' '.join(partial_regexes)
    m = re.match(regex, cmd)
    if m:
        return f(fs, *m.groups())
    elif cmd_name == 'help':
        return fs, get_help()
    else:
        return fs, 'ERROR: ' + syntax_help(cmd_name)

def syntax_help(cmd_name):
    commands = get_commands()
    f, arg_names = commands[cmd_name]
    arg_syntax = ' '.join('<' + a + '>' for a in arg_names)
    return 'syntax: %s %s' % (cmd_name, arg_syntax)

def fs_new():
    fs = {
        '/': directory([])
    }
    return fs

def fs_help(fs, cmd_name):
    return fs, syntax_help(cmd_name)

def fs_mkdir(fs, fn):
    if fn in fs:
        return fs, 'ERROR: file already exists'
    dir_path = os.path.dirname(fn)
    if not is_directory(fs, dir_path):
        msg = 'ERROR: %s is not a directory' % (dir_path,)
        return fs, msg
    new_fs = fs.copy()
    new_dir = directory({fn}.union(fs[dir_path]['fns']))
    new_fs[dir_path] = new_dir
    new_fs[fn] = directory([])
    msg = 'directory created'
    return new_fs, msg

def fs_ls(fs, fn):
    if fn not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    if not is_directory(fs, fn):
        return fs, 'ERROR: %s is not a directory' % (fn,)
    fns = fs[fn]['fns']
    if not fns:
        return fs, 'WARNING: directory is empty'
    msg = '\n'.join('* ' + fn for fn in sorted(fns))
    return fs, msg

def fs_rm(fs, fn):
    if fn not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    new_fs = fs.copy()
    new_fs.pop(fn)
    msg = 'removed'
    return new_fs, msg

def fs_write(fs, fn, content):
    if fn in fs:
        msg = 'ERROR: file already exists'
        return fs, msg
    dir_path = os.path.dirname(fn)
    if not is_directory(fs, dir_path):
        msg = 'ERROR: %s is not a directory' % (dir_path,)
        return fs, msg
    new_fs = fs.copy()
    new_dir = directory({fn}.union(fs[dir_path]['fns']))
    new_fs[dir_path] = new_dir
    new_fs[fn] = text_file(content)
    msg = 'file written'
    return new_fs, msg

def fs_read(fs, fn):
    if fn not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    val = fs[fn]['content']
    return fs, val

def directory(fns):
    return dict(kind='dir', fns=set(fns))

def text_file(content):
    return dict(kind='text', content=content)

def is_directory(fs, fn):
    if fn not in fs:
        return False
    return fs[fn]['kind'] == 'dir'

handler_class = VirtualFsHandler

if __name__ == '__main__':
    # We eventually want to test bots with a "real" testing
    # framework.
    test()
