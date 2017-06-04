# See readme.md for instructions on running this code.

import re
import os

class VirtualFsHandler(object):
    def usage(self):
        return get_help()

    def handle_message(self, message, client, state_handler):
        command = message['content']
        if command == "":
            command = "help"
        sender = message['sender_email']

        state = state_handler.get_state()
        if state is None:
            state = {}

        recipient = message['display_recipient']
        if isinstance(recipient, list):  # If not a stream, then hash on list of emails
            recipient = " ".join([x['email'] for x in recipient])

        if recipient not in state:
            state[recipient] = fs_new()
        fs = state[recipient]
        if sender not in fs['user_paths']:
            fs['user_paths'][sender] = '/'
        fs, msg = fs_command(fs, sender, command)
        prependix = '{}:\n'.format(sender)
        msg = prependix + msg
        state[recipient] = fs
        state_handler.set_state(state)

        client.send_reply(message, msg)


def get_help():
    return '''
This bot implements a virtual file system for a stream.
The locations of text are persisted for the lifetime of the bot
running, and if you rename a stream, you will lose the info.
Example commands:

```
@mention-bot sample_conversation: sample conversation with the bot
@mention-bot mkdir: create a directory
@mention-bot ls: list a directory
@mention-bot cd: change directory
@mention-bot pwd: show current path
@mention-bot write: write text
@mention-bot read: read text
@mention-bot rm: remove a file
@mention-bot rmdir: remove a directory
```
Use commands like `@mention-bot help write` for more details on specific
commands.
'''

def sample_conversation():
    return [
        ('cd /\nCurrent path: /\n\n'),
        ('cd /home\nERROR: invalid path\n\n'),
        ('cd .\nERROR: invalid path\n\n'),
        ('mkdir home\ndirectory created\n\n'),
        ('cd home\nCurrent path: /home/\n\n'),
        ('cd /home/\nCurrent path: /home/\n\n'),
        ('mkdir stuff/\nERROR: stuff/ is not a valid name\n\n'),
        ('mkdir stuff\ndirectory created\n\n'),
        ('write stuff/file1 something\nfile written\n\n'),
        ('read stuff/file1\nsomething\n\n'),
        ('read /home/stuff/file1\nsomething\n\n'),
        ('read home/stuff/file1\nERROR: file does not exist\n\n'),
        ('pwd    \n/home/\n\n'),
        ('pwd bla\nERROR: syntax: pwd\n\n'),
        ('ls bla foo\nERROR: syntax: ls <optional_path>\n\n'),
        ('cd /\nCurrent path: /\n\n'),
        ('rm home\nERROR: /home/ is a directory, file required\n\n'),
        ('rmdir home\nremoved\n\n'),
        ('ls  \nWARNING: directory is empty\n\n'),
        ('cd home\nERROR: invalid path\n\n'),
        ('read /home/stuff/file1\nERROR: file does not exist\n\n'),
        ('cd /\nCurrent path: /\n\n'),
        ('write /foo contents of /foo\nfile written\n\n'),
        ('read /foo\ncontents of /foo\n\n'),
        ('write /bar Contents: bar bar\nfile written\n\n'),
        ('read /bar\nContents: bar bar\n\n'),
        ('write /bar invalid\nERROR: file already exists\n\n'),
        ('rm /bar\nremoved\n\n'),
        ('rm /bar\nERROR: file does not exist\n\n'),
        ('write /bar new bar\nfile written\n\n'),
        ('read /bar\nnew bar\n\n'),
        ('write /yo/invalid whatever\nERROR: /yo is not a directory\n\n'),
        ('mkdir /yo\ndirectory created\n\n'),
        ('read /yo\nERROR: /yo/ is a directory, file required\n\n'),
        ('ls /yo\nWARNING: directory is empty\n\n'),
        ('read /yo/nada\nERROR: file does not exist\n\n'),
        ('write /yo whatever\nERROR: file already exists\n\n'),
        ('write /yo/apple red\nfile written\n\n'),
        ('read /yo/apple\nred\n\n'),
        ('mkdir /yo/apple\nERROR: file already exists\n\n'),
        ('ls /invalid\nERROR: file does not exist\n\n'),
        ('ls /foo\nERROR: /foo is not a directory\n\n'),
        ('ls /\n* /*bar*\n* /*foo*\n* /yo/\n\n'),
        ('invalid command\nERROR: unrecognized command\n\n'),
        ('write\nERROR: syntax: write <path> <some_text>\n\n'),
        ('help' + get_help() + '\n\n'),
        ('help ls\nsyntax: ls <optional_path>\n\n'),
        ('help invalid_command' + get_help() + '\n\n'),
    ]

REGEXES = dict(
    command='(cd|ls|mkdir|read|rmdir|rm|write|pwd)',
    path='(\S+)',
    optional_path='(\S*)',
    some_text='(.+)',
)

def get_commands():
    return {
        'help': (fs_help, ['command']),
        'sample_conversation': (fs_sample_conversation, ['command']),
        'ls': (fs_ls, ['optional_path']),
        'mkdir': (fs_mkdir, ['path']),
        'read': (fs_read, ['path']),
        'rm': (fs_rm, ['path']),
        'rmdir': (fs_rmdir, ['path']),
        'write': (fs_write, ['path', 'some_text']),
        'cd': (fs_cd, ['path']),
        'pwd': (fs_pwd, []),
    }

def fs_command(fs, user, cmd):
    cmd = cmd.strip()
    if cmd == 'help':
        return fs, get_help()
    if cmd == 'sample_conversation':
        return fs, (''.join(sample_conversation()))
    cmd_name = cmd.split()[0]
    cmd_args = cmd[len(cmd_name):].strip()
    commands = get_commands()
    if cmd_name not in commands:
        return fs, 'ERROR: unrecognized command'

    f, arg_names = commands[cmd_name]
    partial_regexes = [REGEXES[a] for a in arg_names]
    regex = ' '.join(partial_regexes)
    regex += '$'
    m = re.match(regex, cmd_args)
    if m:
        return f(fs, user, *m.groups())
    elif cmd_name == 'help':
        return fs, get_help()
    else:
        return fs, 'ERROR: ' + syntax_help(cmd_name)

def syntax_help(cmd_name):
    commands = get_commands()
    f, arg_names = commands[cmd_name]
    arg_syntax = ' '.join('<' + a + '>' for a in arg_names)
    if arg_syntax:
        cmd = cmd_name + ' ' + arg_syntax
    else:
        cmd = cmd_name
    return 'syntax: {}'.format(cmd)

def fs_new():
    fs = {
        '/': directory([]),
        'user_paths': dict()
    }
    return fs

def fs_help(fs, user, cmd_name):
    return fs, syntax_help(cmd_name)

def fs_sample_conversation(fs, user, cmd_name):
    return fs, syntax_help(cmd_name)

def fs_mkdir(fs, user, fn):
    path, msg = make_path(fs, user, fn)
    if msg:
        return fs, msg
    if path in fs:
        return fs, 'ERROR: file already exists'
    dir_path = os.path.dirname(path)
    if not is_directory(fs, dir_path):
        msg = 'ERROR: {} is not a directory'.format(dir_path)
        return fs, msg
    new_fs = fs.copy()
    new_dir = directory({path}.union(fs[dir_path]['fns']))
    new_fs[dir_path] = new_dir
    new_fs[path] = directory([])
    msg = 'directory created'
    return new_fs, msg

def fs_ls(fs, user, fn):
    if fn == '.' or fn == '':
        path = fs['user_paths'][user]
    else:
        path, msg = make_path(fs, user, fn)
        if msg:
            return fs, msg
    if path not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    if not is_directory(fs, path):
        return fs, 'ERROR: {} is not a directory'.format(path)
    fns = fs[path]['fns']
    if not fns:
        return fs, 'WARNING: directory is empty'
    msg = '\n'.join('* ' + nice_path(fs, path) for path in sorted(fns))
    return fs, msg

def fs_pwd(fs, user):
    path = fs['user_paths'][user]
    msg = nice_path(fs, path)
    return fs, msg

def fs_rm(fs, user, fn):
    path, msg = make_path(fs, user, fn)
    if msg:
        return fs, msg
    if path not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    if fs[path]['kind'] == 'dir':
        msg = 'ERROR: {} is a directory, file required'.format(nice_path(fs, path))
        return fs, msg
    new_fs = fs.copy()
    new_fs.pop(path)
    directory = get_directory(path)
    new_fs[directory]['fns'].remove(path)
    msg = 'removed'
    return new_fs, msg

def fs_rmdir(fs, user, fn):
    path, msg = make_path(fs, user, fn)
    if msg:
        return fs, msg
    if path not in fs:
        msg = 'ERROR: directory does not exist'
        return fs, msg
    if fs[path]['kind'] == 'text':
        msg = 'ERROR: {} is a file, directory required'.format(nice_path(fs, path))
        return fs, msg
    new_fs = fs.copy()
    new_fs.pop(path)
    directory = get_directory(path)
    new_fs[directory]['fns'].remove(path)
    for sub_path in new_fs.keys():
        if sub_path.startswith(path+'/'):
            new_fs.pop(sub_path)
    msg = 'removed'
    return new_fs, msg

def fs_write(fs, user, fn, content):
    path, msg = make_path(fs, user, fn)
    if msg:
        return fs, msg
    if path in fs:
        msg = 'ERROR: file already exists'
        return fs, msg
    dir_path = os.path.dirname(path)
    if not is_directory(fs, dir_path):
        msg = 'ERROR: {} is not a directory'.format(dir_path)
        return fs, msg
    new_fs = fs.copy()
    new_dir = directory({path}.union(fs[dir_path]['fns']))
    new_fs[dir_path] = new_dir
    new_fs[path] = text_file(content)
    msg = 'file written'
    return new_fs, msg

def fs_read(fs, user, fn):
    path, msg = make_path(fs, user, fn)
    if msg:
        return fs, msg
    if path not in fs:
        msg = 'ERROR: file does not exist'
        return fs, msg
    if fs[path]['kind'] == 'dir':
        msg = 'ERROR: {} is a directory, file required'.format(nice_path(fs, path))
        return fs, msg
    val = fs[path]['content']
    return fs, val

def fs_cd(fs, user, fn):
    if len(fn) > 1 and fn[-1] == '/':
        fn = fn[:-1]
    path = fn if len(fn) > 0 and fn[0] == '/' else make_path(fs, user, fn)[0]
    if path not in fs:
        msg = 'ERROR: invalid path'
        return fs, msg
    if fs[path]['kind'] == 'text':
        msg = 'ERROR: {} is a file, directory required'.format(nice_path(fs, path))
        return fs, msg
    fs['user_paths'][user] = path
    return fs, "Current path: {}".format(nice_path(fs, path))

def make_path(fs, user, leaf):
    if leaf == '/':
        return ['/', '']
    if leaf.endswith('/'):
        return ['', 'ERROR: {} is not a valid name'.format(leaf)]
    if leaf.startswith('/'):
        return [leaf, '']
    path = fs['user_paths'][user]
    if not path.endswith('/'):
        path += '/'
    path += leaf
    return path, ''

def nice_path(fs, path):
    path_nice = path
    slash = path.rfind('/')
    if path not in fs:
        return 'ERROR: the current directory does not exist'
    if fs[path]['kind'] == 'text':
        path_nice = '{}*{}*'.format(path[:slash+1], path[slash+1:])
    elif path != '/':
        path_nice = '{}/'.format(path)
    return path_nice

def get_directory(path):
    slash = path.rfind('/')
    if slash == 0:
        return '/'
    else:
        return path[:slash]

def directory(fns):
    return dict(kind='dir', fns=set(fns))

def text_file(content):
    return dict(kind='text', content=content)

def is_directory(fs, fn):
    if fn not in fs:
        return False
    return fs[fn]['kind'] == 'dir'

handler_class = VirtualFsHandler
