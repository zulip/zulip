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
import logging

DEFAULT_SITE = "https://humbughq.com"

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
    match_user = re.match(r'([a-zA-Z0-9_]+)\|(.+)', user)
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
            len(line + " " + words[0]) < 50 or
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
    if "subject" in zeph:
        # Truncate the subject to the current limit in Humbug.  No
        # need to do this for stream names, since we're only
        # subscribed to valid stream names.
        message["subject"] = zeph["subject"][:60]
    if zeph['type'] == 'stream':
        # Forward messages sent to -c foo -i bar to stream bar subject "instance"
        if zeph["stream"] == "message":
            message['stream'] = zeph['subject'].lower()
            message['subject'] = "instance %s" % (zeph['subject'],)
        elif zeph["stream"] == "tabbott-test5":
            message['stream'] = zeph['subject'].lower()
            message['subject'] = "test instance %s" % (zeph['subject'],)
        else:
            message["stream"] = zeph["stream"]
    else:
        message["recipient"] = zeph["recipient"]
    message['content'] = unwrap_lines(zeph['content'])

    if options.test_mode and options.site == DEFAULT_SITE:
        logger.debug("Message is: %s" % (str(message),))
        return {'result': "success"}

    return humbug_client.send_message(message)

current_zephyr_subs = set()
def zephyr_bulk_subscribe(subs):
    try:
        zephyr._z.subAll(subs)
    except IOError:
        # Since we haven't added the subscription to
        # current_zephyr_subs yet, we can just return (so that we'll
        # continue processing normal messages) and we'll end up
        # retrying the next time the bot checks its subscriptions are
        # up to date.
        logger.exception("Error subscribing to streams (will retry automatically):")
        logging.debug("Streams were: %s" % ((cls for cls, instance, recipient in subs),))
        return
    for (cls, instance, recipient) in subs:
        current_zephyr_subs.add(cls)

def update_subscriptions_from_humbug():
    try:
        res = humbug_client.get_public_streams()
        streams = res["streams"]
    except:
        logger.exception("Error getting public streams:")
        return
    streams_to_subscribe = []
    for stream in streams:
        if stream in current_zephyr_subs:
            continue
        streams_to_subscribe.append((stream.encode("utf-8"), "*", "*"))
    if len(streams_to_subscribe) > 0:
        zephyr_bulk_subscribe(streams_to_subscribe)

def maybe_restart_mirroring_script():
    if os.stat(os.path.join(options.root_path, "stamps", "restart_stamp")).st_mtime > start_time or \
            ((options.user == "tabbott" or options.user == "tabbott/extra") and
             os.stat(os.path.join(options.root_path, "stamps", "tabbott_stamp")).st_mtime > start_time):
        logger.warning("")
        logger.warning("zephyr mirroring script has been updated; restarting...")
        os.kill(child_pid, signal.SIGTERM)
        while True:
            try:
                if bot_name == "extra_mirror.py":
                    os.execvp(os.path.join(options.root_path, "extra_mirror.py"), sys.argv)
                os.execvp(os.path.join(options.root_path, "user_root", "zephyr_mirror.py"), sys.argv)
            except:
                logger.exception("Error restarting mirroring script; trying again... Traceback:")
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
                logger.exception("Error relaying zephyr:")
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
        logger.debug("Skipping message we got from Humbug!")
        return

    zephyr_class = notice.cls.lower()

    if (zephyr_class == "message" and notice.recipient != ""):
        is_personal = True
        if body.startswith("CC:"):
            is_huddle = True
            # Map "CC: sipbtest espuser" => "starnine@mit.edu,espuser@mit.edu"
            huddle_recipients = [to_humbug_username(x.strip()) for x in
                                 body.split("\n")[0][4:].split()]
            if notice.sender not in huddle_recipients:
                huddle_recipients.append(to_humbug_username(notice.sender))
            body = body.split("\n", 1)[1]
    if (zephyr_class == "mail" and notice.instance.lower() == "inbox"):
        is_personal = True

    # Drop messages not to the listed subscriptions
    if (zephyr_class not in current_zephyr_subs) and not \
            (is_personal and options.forward_personals):
        logger.debug("Skipping ... %s/%s/%s" %
                     (zephyr_class, notice.instance, is_personal))
        return

    zeph = { 'time'      : str(notice.time),
             'sender'    : notice.sender,
             'zsig'      : zsig,  # logged here but not used by app
             'content'   : body }
    if is_huddle:
        zeph['type'] = 'private'
        zeph['recipient'] = huddle_recipients
    elif is_personal:
        zeph['type'] = 'private'
        zeph['recipient'] = to_humbug_username(notice.recipient)
    else:
        zeph['type'] = 'stream'
        zeph['stream'] = zephyr_class
        if notice.instance.strip() != "":
            zeph['subject'] = notice.instance
        else:
            zeph["subject"] = '(instance "%s")' % (notice.instance,)

    # Add instances in for instanced personals
    if zeph['type'] == "private" and notice.instance.lower() != "personal":
        zeph["content"] = "[-i %s]" % (notice.instance,) + "\n" + zeph["content"]

    zeph = decode_unicode_byte_strings(zeph)

    logger.info("Received a message on %s/%s from %s..." %
                (zephyr_class, notice.instance, notice.sender))
    if log is not None:
        log.write(simplejson.dumps(zeph) + '\n')
        log.flush()

    res = send_humbug(zeph)
    if res.get("result") != "success":
        logger.error("Error relaying zephyr:\n%s\n%s" %(zeph, res))

def decode_unicode_byte_strings(zeph):
    for field in zeph.keys():
        if isinstance(zeph[field], str):
            try:
                decoded = zeph[field].decode("utf-8")
            except:
                decoded = zeph[field].decode("iso-8859-1")
            zeph[field] = decoded
    return zeph

def zephyr_subscribe_autoretry(sub):
    while True:
        try:
            zephyr.Subscriptions().add(sub)
            return
        except IOError:
            # Probably a SERVNAK from the zephyr server, but print the
            # traceback just in case it's something else
            logger.exception("Error subscribing to personals (retrying).  Traceback:")
            time.sleep(1)

def zephyr_to_humbug(options):
    if options.forward_class_messages:
        update_subscriptions_from_humbug()
    if options.forward_personals:
        # Subscribe to personals; we really can't operate without
        # those subscriptions, so just retry until it works.
        zephyr_subscribe_autoretry(("message", "*", "%me%"))
        if subscribed_to_mail_messages():
            zephyr_subscribe_autoretry(("mail", "inbox", "%me%"))

    if options.resend_log_path is not None:
        with open(options.resend_log_path, 'r') as log:
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
                    logger.info("sending saved message to %s from %s..." %
                                (zeph.get('stream', zeph.get('recipient')),
                                 zeph['sender']))
                    send_humbug(zeph)
                except:
                    logger.exception("Could not send saved zephyr:")
                    time.sleep(2)

    logger.info("Starting receive loop.")

    if options.log_path is not None:
        with open(options.log_path, 'a') as log:
            process_loop(log)
    else:
        process_loop(None)

def forward_to_zephyr(message):
    zsig = u"%s@(@color(blue))" % (zsig_fullname,)
    if ' dot ' in zsig:
        logger.error("Error computing zsig for %s!" % (message["sender_email"],))
        return

    wrapped_content = "\n".join("\n".join(textwrap.wrap(line))
            for line in message["content"].split("\n"))

    logger.info("Forwarding message from %s" %  (message["sender_email"],))
    if message['type'] == "stream":
        zephyr_class = message["display_recipient"]
        instance = message["subject"]

        match_whitespace_instance = re.match(r'^\(instance "(\s*)"\)$', instance)
        if match_whitespace_instance:
            # Forward messages sent to '(instance "WHITESPACE")' back to the
            # appropriate WHITESPACE instance for bidirectional mirroring
            instance = match_whitespace_instance.group(1)
        elif (instance == "instance %s" % (zephyr_class,) or
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

    if options.test_mode:
        logger.debug("Would have forwarded: %s\n%s" %
                     (zwrite_args, wrapped_content.encode("utf-8")))
        return

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
            logger.warning("Skipping out of order message: %s < %s" %
                           (message["timestamp"], timestamp_now))
            return
        try:
            forward_to_zephyr(message)
        except:
            # Don't let an exception forwarding one message crash the
            # whole process
            logger.exception("Error forwarding message:")

def humbug_to_zephyr(options):
    # Sync messages from zephyr to humbug
    logger.info("Starting syncing messages.")
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
    return name != ""

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

def fetch_fullname(username):
    try:
        proc = subprocess.Popen(['hesinfo', username, 'passwd'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, _err_unused = proc.communicate()
        if proc.returncode == 0:
            return out.split(':')[4].split(',')[0]
    except:
        logger.exception("Error getting fullname for %s:" % (username,))

    return username

def configure_logger(direction_name):
    if options.forward_class_messages:
        if options.test_mode:
            log_file = "/home/humbug/test-mirror-log"
        else:
            log_file = "/home/humbug/mirror-log"
    else:
        log_file = "/tmp/humbug-log." + options.user
    logger = logging.getLogger(__name__)
    log_format = "%(asctime)s " + direction_name + ": %(message)s"
    formatter = logging.Formatter(log_format)
    logging.basicConfig(format=log_format)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('--forward-class-messages',
                      dest='forward_class_messages',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--resend-log',
                      dest='resend_log_path',
                      default=None,
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--enable-log',
                      dest='log_path',
                      default=None,
                      help=optparse.SUPPRESS_HELP,
                      action='store')
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
                      default=DEFAULT_SITE,
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--user',
                      dest='user',
                      default=os.environ["USER"],
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--root-path',
                      dest='root_path',
                      default="/afs/athena.mit.edu/user/t/a/tabbott/for_friends",
                      help=optparse.SUPPRESS_HELP,
                      action='store')
    parser.add_option('--test-mode',
                      dest='test_mode',
                      default=False,
                      help=optparse.SUPPRESS_HELP,
                      action='store_true')
    parser.add_option('--api-key-file',
                      dest='api_key_file',
                      default=os.path.join(os.environ["HOME"], "Private", ".humbug-api-key"),
                      action='store')
    (options, args) = parser.parse_args()

    sys.path[:0] = [options.root_path, os.path.join(options.root_path, "python-zephyr"),
                    os.path.join(options.root_path, "python-zephyr/build/lib.linux-x86_64-2.6/")]

    # In case this is an automated restart of the mirroring script,
    # and we have lost AFS tokens, first try reading the API key from
    # the environment so that we can skip doing a filesystem read.
    if os.environ.get("HUMBUG_API_KEY") is not None:
        api_key = os.environ.get("HUMBUG_API_KEY")
    else:
        if not os.path.exists(options.api_key_file):
            print "\n".join(textwrap.wrap("""\
Could not find API key file.
You need to either place your api key file at %s,
or specify the --api-key-file option.""" % (options.api_key_file,)))
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
    if not options.test_mode:
        proc = subprocess.Popen(['pgrep', '-U', os.environ["USER"], "-f", bot_name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, _err_unused = proc.communicate()
        for pid in out.split():
            if int(pid.strip()) != os.getpid():
                # Another copy of zephyr_mirror.py!  Kill it.
                print "Killing duplicate zephyr_mirror process %s" % (pid,)
                os.kill(int(pid), signal.SIGKILL)

    child_pid = os.fork()
    if child_pid == 0:
        # Run the humbug => zephyr mirror in the child
        logger = configure_logger("humbug=>zephyr")
        zsig_fullname = fetch_fullname(options.user)
        humbug_to_zephyr(options)
        sys.exit(0)

    import zephyr
    while True:
        try:
            # zephyr.init() tries to clear old subscriptions, and thus
            # sometimes gets a SERVNAK from the server
            zephyr.init()
            break
        except IOError:
            traceback.print_exc()
            time.sleep(1)
    logger = configure_logger("zephyr=>humbug")
    zephyr_to_humbug(options)
