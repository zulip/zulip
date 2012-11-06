#!/usr/bin/python
# Copyright (C) 2012 Humbug, Inc.  All rights reserved.
import sys
import traceback
import simplejson
import re
import time
import subprocess
import optparse
import os
import datetime
import textwrap
import signal

root_path = "/mit/tabbott/for_friends"
sys.path[:0] = [root_path, root_path + "/python-zephyr",
                root_path + "/python-zephyr/build/lib.linux-x86_64-2.6/"]

def to_humbug_username(zephyr_username):
    if "@" in zephyr_username:
        (user, realm) = zephyr_username.split("@")
    else:
        (user, realm) = (zephyr_username, "ATHENA.MIT.EDU")
    if realm.upper() == "ATHENA.MIT.EDU":
        return user.lower() + "@mit.edu"
    return user.lower() + "|" + realm.upper() + "@mit.edu"

def to_zephyr_username(humbug_username):
    (user, realm) = humbug_username.split("@")
    if "|" not in user:
        return user.lower() + "@ATHENA.MIT.EDU"
    match_user = re.match(r'([a-zA-Z0-9_]+)\|(.+)@mit\.edu', user)
    if not match_user:
        raise Exception("Could not parse Zephyr realm for cross-realm user %s" % (humbug_username,))
    return match_user.group(1).lower() + "@" + match_user.group(2).upper()

# Checks whether the pair of adjacent lines would have been
# linewrapped together, had they been intended to be parts of the same
# paragraph.  Our check is whether if you move the first word on the
# 2nd line onto the first line, the resulting line is either (1)
# significantly shorter than the following line (which, if they were
# in the same paragraph, should have been wrapped in a way consistent
# with how the previous line was wrapped) or (2) shorter than 60
# characters (our assumed minimum linewrapping threshhold for Zephyr)
# or (3) the first word of the next line is longer than this entire
# line.
def different_paragraph(line, next_line):
    words = next_line.split()
    return (len(line + " " + words[0]) < len(next_line) * 0.8 or
            len(line + " " + words[0]) < 60 or
            len(line) < len(words[0]))

# Linewrapping algorithm based on:
# http://gcbenison.wordpress.com/2011/07/03/a-program-to-intelligently-remove-carriage-returns-so-you-can-paste-text-without-having-it-look-awful/
def unwrap_lines(body):
    lines = body.split("\n")
    result = ""
    previous_line = lines[0]
    for line in lines[1:]:
        line = line.rstrip()
        if (re.match(r'^\W', line, flags=re.UNICODE)
            and re.match(r'^\W', previous_line, flags=re.UNICODE)):
            result += previous_line + "\n"
        elif (line == "" or
            previous_line == "" or
            re.match(r'^\W', line, flags=re.UNICODE) or
            different_paragraph(previous_line, line)):
            # Use 2 newlines to separate sections so that we
            # trigger proper Markdown processing on things like
            # bulleted lists
            result += previous_line + "\n\n"
        else:
            result += previous_line + " "
        previous_line = line
    result += previous_line
    return result

def send_humbug(zeph):
    message = {}
    if options.forward_class_messages:
        message["forged"] = "yes"
    message['type'] = zeph['type']
    message['time'] = zeph['time']
    message['sender'] = to_humbug_username(zeph['sender'])
    message['fullname']  = username_to_fullname(zeph['sender'])
    message['shortname'] = zeph['sender'].split('@')[0]
    if "subject" in zeph:
        # Truncate the subject to the current limit in Humbug.  No
        # need to do this for stream names, since we're only
        # subscribed to valid stream names.
        message["subject"] = zeph["subject"][:60]
    if zeph['type'] == 'stream':
        # Forward messages sent to -c foo -i bar to stream bar subject "instance"
        if zeph["stream"] == "message":
            message['stream'] = zeph['subject'].lower()
            message['subject'] = "instance %s" % (zeph['subject'])
        elif zeph["stream"] == "tabbott-test5":
            message['stream'] = zeph['subject'].lower()
            message['subject'] = "test instance %s" % (zeph['subject'])
        else:
            message["stream"] = zeph["stream"]
    else:
        message["recipient"] = zeph["recipient"]
    message['content'] = unwrap_lines(zeph['content'])

    return humbug_client.send_message(message)

def fetch_fullname(username):
    try:
        match_user = re.match(r'([a-zA-Z0-9_]+)@mit\.edu', username)
        if match_user:
            proc = subprocess.Popen(['hesinfo', match_user.group(1), 'passwd'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, _err_unused = proc.communicate()
            if proc.returncode == 0:
                return out.split(':')[4].split(',')[0]
    except:
        print >>sys.stderr, '%s: zephyr=>humbug: Error getting fullname for %s' % \
            (datetime.datetime.now(), username)
        traceback.print_exc()

    if "@" not in username:
        return username
    (user, realm) = username.split("@")
    if realm.upper() == "MIT.EDU":
        return user
    return user.lower() + "@" + realm.upper()

fullnames = {}
def username_to_fullname(username):
    if username not in fullnames:
        fullnames[username] = fetch_fullname(username)
    return fullnames[username]

current_zephyr_subs = set()
def ensure_subscribed(sub):
    if sub in current_zephyr_subs:
        return
    subs.add((sub, '*', '*'))
    current_zephyr_subs.add(sub)

def update_subscriptions_from_humbug():
    try:
        res = humbug_client.get_public_streams()
        streams = res["streams"]
    except:
        print "%s: Error getting public streams:" % (datetime.datetime.now())
        traceback.print_exc()
        return
    for stream in streams:
        ensure_subscribed(stream)

def maybe_restart_mirroring_script():
    if os.stat(root_path + "/stamps/restart_stamp").st_mtime > start_time or \
            ((options.user == "tabbott" or options.user == "tabbott/extra") and
             os.stat(root_path + "/stamps/tabbott_stamp").st_mtime > start_time):
        print
        print "%s: zephyr mirroring script has been updated; restarting..." % \
            (datetime.datetime.now())
        os.kill(child_pid, signal.SIGTERM)
        while True:
            try:
                if bot_name == "extra_mirror.py":
                    os.execvp(root_path + "/extra_mirror.py", sys.argv)
                os.execvp(root_path + "/user_root/zephyr_mirror.py", sys.argv)
            except:
                print "Error restarting, trying again."
                traceback.print_exc()
                time.sleep(1)

def process_loop(log):
    sleep_count = 0
    sleep_time = 0.1
    while True:
        notice = zephyr.receive(block=False)
        if notice is not None:
            try:
                process_notice(notice, log)
            except:
                print >>sys.stderr, '%s: zephyr=>humbug: Error relaying zephyr' % \
                    (datetime.datetime.now())
                traceback.print_exc()
                time.sleep(2)

        maybe_restart_mirroring_script()

        time.sleep(sleep_time)
        sleep_count += sleep_time
        if sleep_count > 15:
            sleep_count = 0
            if options.forward_class_messages:
                # Ask the Humbug server about any new classes to subscribe to
                update_subscriptions_from_humbug()

def parse_zephyr_body(zephyr_data):
    try:
        (zsig, body) = zephyr_data.split("\x00", 1)
    except ValueError:
        (zsig, body) = ("", zephyr_data)
    return (zsig, body)

def process_notice(notice, log):
    (zsig, body) = parse_zephyr_body(notice.message)
    is_personal = False
    is_huddle = False

    if notice.opcode == "PING":
        # skip PING messages
        return

    if zsig.endswith("@(@color(blue))"):
        print "%s: zephyr=>humbug: Skipping message we got from Humbug!" % \
            (datetime.datetime.now())
        return

    zephyr_class = notice.cls.lower()

    if (zephyr_class == "message" and notice.recipient != ""):
        is_personal = True
        if body.startswith("CC:"):
            is_huddle = True
            # Map "CC: sipbtest espuser" => "starnine@mit.edu,espuser@mit.edu"
            huddle_recipients_list = [to_humbug_username(x.strip()) for x in
                                      body.split("\n")[0][4:].split()]
            if notice.sender not in huddle_recipients_list:
                huddle_recipients_list.append(to_humbug_username(notice.sender))
            huddle_recipients = ",".join(huddle_recipients_list)
            body = body.split("\n", 1)[1]
    if (zephyr_class == "mail" and notice.instance.lower() == "inbox"):
        is_personal = True

    # Drop messages not to the listed subscriptions
    if (zephyr_class not in current_zephyr_subs) and not \
            (is_personal and options.forward_personals):
        print "%s: zephyr=>humbug: Skipping ... %s/%s/%s" % \
            (datetime.datetime.now(), zephyr_class, notice.instance, is_personal)
        return

    zeph = { 'time'      : str(notice.time),
             'sender'    : notice.sender,
             'zsig'      : zsig,  # logged here but not used by app
             'content'   : body }
    if is_huddle:
        zeph['type'] = 'personal'
        zeph['recipient'] = huddle_recipients
    elif is_personal:
        zeph['type'] = 'personal'
        zeph['recipient'] = to_humbug_username(notice.recipient)
    else:
        zeph['type'] = 'stream'
        zeph['stream'] = zephyr_class
        if notice.instance != "":
            zeph['subject'] = notice.instance
        else:
            zeph["subject"] = "personal"

    # Add instances in for instanced personals
    if zeph['type'] == "personal" and notice.instance.lower() != "personal":
        zeph["content"] = "[-i %s]" % (notice.instance,) + "\n" + zeph["content"]

    zeph = decode_unicode_byte_strings(zeph)

    print "%s: zephyr=>humbug: received a message on %s/%s from %s..." % \
        (datetime.datetime.now(), zephyr_class, notice.instance, notice.sender)
    log.write(simplejson.dumps(zeph) + '\n')
    log.flush()

    res = send_humbug(zeph)
    if res.get("result") != "success":
        print >>sys.stderr, 'Error relaying zephyr'
        print zeph
        print res

def decode_unicode_byte_strings(zeph):
    for field in zeph.keys():
        if isinstance(zeph[field], str):
            try:
                decoded = zeph[field].decode("utf-8")
            except:
                decoded = zeph[field].decode("iso-8859-1")
            zeph[field] = decoded
    return zeph

def zephyr_to_humbug(options):
    if options.forward_class_messages:
        update_subscriptions_from_humbug()
    if options.forward_personals:
        subs.add(("message", "*", "%me%"))
        if subscribed_to_mail_messages():
            subs.add(("mail", "inbox", "%me%"))

    if options.resend_log:
        with open('/mit/tabbott/Private/zephyrs', 'r') as log:
            for ln in log:
                try:
                    zeph = simplejson.loads(ln)
                    # New messages added to the log shouldn't have any
                    # elements of type str (they should already all be
                    # unicode), but older messages in the log are
                    # still of type str, so convert them before we
                    # send the message
                    zeph = decode_unicode_byte_strings(zeph)
                    # Handle importing older zephyrs in the logs
                    # where it isn't called a "stream" yet
                    if "class" in zeph:
                        zeph["stream"] = zeph["class"]
                    if "instance" in zeph:
                        zeph["subject"] = zeph["instance"]
                    print "%s: zephyr=>humbug: sending saved message to %s from %s..." % \
                        (datetime.datetime.now(), zeph.get('stream', zeph.get('recipient')),
                         zeph['sender'])
                    send_humbug(zeph)
                except:
                    print >>sys.stderr, 'Could not send saved zephyr'
                    traceback.print_exc()
                    time.sleep(2)

    print "%s: zephyr=>humbug: Starting receive loop." % (datetime.datetime.now(),)

    if options.enable_log:
        log_file = "/mit/tabbott/Private/zephyrs"
    else:
        log_file = "/dev/null"

    with open(log_file, 'a') as log:
        process_loop(log)

def forward_to_zephyr(message):
    zsig = u"%s@(@color(blue))" % (username_to_fullname(message["sender_email"]))
    if ' dot ' in zsig:
        print "%s: humbug=>zephyr: ERROR!  Couldn't compute zsig for %s!" % \
            (datetime.datetime.now(), message["sender_email"])
        return

    wrapped_content = "\n".join("\n".join(textwrap.wrap(line))
            for line in message["content"].split("\n"))

    print "%s: humbug=>zephyr: Forwarding message from %s" % \
        (datetime.datetime.now(), message["sender_email"])
    if message['type'] == "stream":
        zephyr_class = message["display_recipient"]
        instance = message["subject"]
        if (instance == "instance %s" % (zephyr_class,) or
            instance == "test instance %s" % (zephyr_class,)):
            # Forward messages to e.g. -c -i white-magic back from the
            # place we forward them to
            if instance.startswith("test"):
                instance = zephyr_class
                zephyr_class = "tabbott-test5"
            else:
                instance = zephyr_class
                zephyr_class = "message"
        zwrite_args = ["zwrite", "-s", zsig, "-c", zephyr_class, "-i", instance]
    elif message['type'] == "personal":
        recipient = to_zephyr_username(message["display_recipient"]["email"])
        zwrite_args = ["zwrite", "-s", zsig, recipient]
    elif message['type'] == "huddle":
        zwrite_args = ["zwrite", "-s", zsig, "-C"]
        zwrite_args.extend([to_zephyr_username(user["email"]).replace("@ATHENA.MIT.EDU", "")
                            for user in message["display_recipient"]])

    p = subprocess.Popen(zwrite_args, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE)
    p.communicate(input=wrapped_content.encode("utf-8"))

def maybe_forward_to_zephyr(message):
    if (message["sender_email"] == options.user + "@mit.edu"):
        if not ((message["type"] == "stream") or
                (message["type"] == "personal" and
                 message["display_recipient"]["email"].lower().endswith("mit.edu")) or
                (message["type"] == "huddle" and
                 False not in [u["email"].lower().endswith("mit.edu") for u in
                               message["display_recipient"]])):
            # Don't try forward personals/huddles with non-MIT users
            # to MIT Zephyr.
            return
        timestamp_now = datetime.datetime.now().strftime("%s")
        if float(message["timestamp"]) < float(timestamp_now) - 15:
            print "%s humbug=>zephyr: Alert!  Out of order message: %s < %s" % \
                (datetime.datetime.now(), message["timestamp"], timestamp_now)
            return
        try:
            forward_to_zephyr(message)
        except:
            # Don't let an exception forwarding one message crash the
            # whole process
            traceback.print_exc()

def humbug_to_zephyr(options):
    # Sync messages from zephyr to humbug
    print "%s: humbug=>zephyr: Starting syncing messages." % (datetime.datetime.now(),)
    humbug_client.call_on_each_message(maybe_forward_to_zephyr,
                                       options={"mirror": 'zephyr_mirror'})

def subscribed_to_mail_messages():
    # In case we have lost our AFS tokens and those won't be able to
    # parse the Zephyr subs file, first try reading in result of this
    # query from the environment so we can avoid the filesystem read.
    stored_result = os.environ.get("HUMBUG_FORWARD_MAIL_ZEPHYRS")
    if stored_result is not None:
        return stored_result == "True"
    for (cls, instance, recipient) in parse_zephyr_subs(verbose=False):
        if (cls.lower() == "mail" and instance.lower() == "inbox"):
            os.environ["HUMBUG_FORWARD_MAIL_ZEPHYRS"] = "True"
            return True
    os.environ["HUMBUG_FORWARD_MAIL_ZEPHYRS"] = "False"
    return False

def add_humbug_subscriptions(verbose):
    zephyr_subscriptions = set()
    skipped = set()
    for (cls, instance, recipient) in parse_zephyr_subs(verbose=verbose):
        if cls == "message":
            if recipient != "*":
                # We already have a (message, *, you) subscription, so
                # these are redundant
                continue
            # We don't support subscribing to (message, *)
            if instance == "*":
                if recipient == "*":
                    skipped.add((cls, instance, recipient, "subscribing to all of class message is not supported."))
                continue
            # If you're on -i white-magic on zephyr, get on stream white-magic on humbug
            # instead of subscribing to stream "message" on humbug
            zephyr_subscriptions.add(instance)
            continue
        elif cls == "mail" and instance == "inbox":
            # We forward mail zephyrs, so no need to print a warning.
            continue
        elif len(cls) > 30:
            skipped.add((cls, instance, recipient, "Class longer than 30 characters"))
            continue
        elif instance != "*":
            skipped.add((cls, instance, recipient, "Unsupported non-* instance"))
            continue
        elif recipient != "*":
            skipped.add((cls, instance, recipient, "Unsupported non-* recipient."))
            continue
        zephyr_subscriptions.add(cls)

    if len(zephyr_subscriptions) != 0:
        res = humbug_client.subscribe(list(zephyr_subscriptions))
        if res.get("result") != "success":
            print "Error subscribing to streams:"
            print res["msg"]
            return

        already = res.get("already_subscribed")
        new = res.get("subscribed")
        if verbose:
            if already is not None and len(already) > 0:
                print
                print "Already subscribed to:", ", ".join(already)
            if new is not None and len(new) > 0:
                print
                print "Successfully subscribed to:",  ", ".join(new)

    if len(skipped) > 0:
        if verbose:
            print
            print "\n".join(textwrap.wrap("""\
You have some lines in ~/.zephyr.subs that could not be
synced to your Humbug subscriptions because they do not
use "*" as both the instance and recipient and not one of
the special cases (e.g. personals and mail zephyrs) that
Humbug has a mechanism for forwarding.  Humbug does not
allow subscribing to only some subjects on a Humbug
stream, so this tool has not created a corresponding
Humbug subscription to these lines in ~/.zephyr.subs:
"""))
            print

    for (cls, instance, recipient, reason) in skipped:
        if verbose:
            if reason != "":
                print "  [%s,%s,%s] (%s)" % (cls, instance, recipient, reason)
            else:
                print "  [%s,%s,%s]" % (cls, instance, recipient, reason)
    if len(skipped) > 0:
        if verbose:
            print
            print "\n".join(textwrap.wrap("""\
If you wish to be subscribed to any Humbug streams related
to these .zephyrs.subs lines, please do so via the Humbug
web interface.
"""))
            print

def valid_stream_name(name):
    return re.match(r'^[\w.][\w. -]*$', name, flags=re.UNICODE)

def parse_zephyr_subs(verbose=False):
    zephyr_subscriptions = set()
    subs_file = os.path.join(os.environ["HOME"], ".zephyr.subs")
    if not os.path.exists(subs_file):
        if verbose:
            print >>sys.stderr, "Couldn't find ~/.zephyr.subs!"
        return []

    for line in file(subs_file, "r").readlines():
        line = line.strip()
        if len(line) == 0:
            continue
        try:
            (cls, instance, recipient) = line.split(",")
            cls = cls.replace("%me%", options.user)
            instance = instance.replace("%me%", options.user)
            recipient = recipient.replace("%me%", options.user)
            if not valid_stream_name(cls):
                if verbose:
                    print >>sys.stderr, "Skipping subscription to unsupported class name: [%s]" % (line,)
                continue
        except:
            if verbose:
                print >>sys.stderr, "Couldn't parse ~/.zephyr.subs line: [%s]" % (line,)
            continue
        zephyr_subscriptions.add((cls.strip(), instance.strip(), recipient.strip()))
    return zephyr_subscriptions

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('--forward-class-messages',
                      dest='forward_class_messages',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--resend-log',
                      dest='resend_log',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--enable-log',
                      dest='enable_log',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--no-forward-personals',
                      dest='forward_personals',
                      help=optparse.SUPPRESS_HELP,
                      default=True,
                      action='store_false')
    parser.add_option('--forward-from-humbug',
                      dest='forward_from_humbug',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--verbose',
                      dest='verbose',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--sync-subscriptions',
                      dest='sync_subscriptions',
                      default=False,
                      action='store_true')
    parser.add_option('--site',
                      dest='site',
                      default="https://humbughq.com",
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--user',
                      dest='user',
                      default=os.environ["USER"],
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--api-key-file',
                      dest='api_key_file',
                      default=os.path.join(os.environ["HOME"], "Private", ".humbug-api-key"),
                      action='store')
    (options, args) = parser.parse_args()

    # In case this is an automated restart of the mirroring script,
    # and we have lost AFS tokens, first try reading the API key from
    # the environment so that we can skip doing a filesystem read.
    if os.environ.get("HUMBUG_API_KEY") is not None:
        api_key = os.environ.get("HUMBUG_API_KEY")
    else:
        if not os.path.exists(options.api_key_file):
            print textwrap.wrap("Could not find API key file. " +
                                "You need to either place your api key file at %s, " +
                                "or specify the --api-key-file option." % (options.api_key_file))
            sys.exit(1)
        api_key = file(options.api_key_file).read().strip()
        # Store the API key in the environment so that our children
        # don't need to read it in
        os.environ["HUMBUG_API_KEY"] = api_key

    import api.common
    humbug_client = api.common.HumbugAPI(email=options.user + "@mit.edu",
                                         api_key=api_key,
                                         verbose=True,
                                         client="zephyr_mirror",
                                         site=options.site)

    start_time = time.time()

    if options.sync_subscriptions:
        print "Syncing your ~/.zephyr.subs to your Humbug Subscriptions!"
        add_humbug_subscriptions(True)
        sys.exit(0)

    if options.forward_from_humbug:
        print "This option is obsolete."
        sys.exit(0)

    # First check that there are no other bots running
    cmdline = " ".join(sys.argv)
    if "extra_mirror" in cmdline:
        bot_name = "extra_mirror.py"
    else:
        bot_name = "zephyr_mirror.py"
    proc = subprocess.Popen(['pgrep', '-U', os.environ["USER"], "-f", bot_name],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, _err_unused = proc.communicate()
    for pid in out.split():
        if int(pid.strip()) != os.getpid():
            # Another copy of zephyr_mirror.py!  Kill it.
            print "Killing duplicate zephyr_mirror process %s" % pid
            os.kill(int(pid), signal.SIGKILL)

    child_pid = os.fork()
    if child_pid == 0:
        # Run the humbug => zephyr mirror in the child
        humbug_to_zephyr(options)
        sys.exit(0)

    import zephyr
    zephyr.init()
    subs = zephyr.Subscriptions()
    zephyr_to_humbug(options)
