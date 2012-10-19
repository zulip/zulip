#!/usr/bin/python
import urllib
import sys
import logging
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
from urllib2 import HTTPError

root_path = "/mit/tabbott/for_friends"
sys.path.append(root_path + "/python-zephyr")
sys.path.append(root_path + "/python-zephyr/build/lib.linux-x86_64-2.6/")

parser = optparse.OptionParser()
parser.add_option('--forward-class-messages',
                  dest='forward_class_messages',
                  default=False,
                  action='store_true')
parser.add_option('--resend-log',
                  dest='resend_log',
                  default=False,
                  action='store_true')
parser.add_option('--enable-log',
                  dest='enable_log',
                  default=False,
                  action='store_true')
parser.add_option('--no-forward-personals',
                  dest='forward_personals',
                  default=True,
                  action='store_false')
parser.add_option('--forward-from-humbug',
                  dest='forward_from_humbug',
                  default=False,
                  action='store_true')
parser.add_option('--verbose',
                  dest='verbose',
                  default=False,
                  action='store_true')
parser.add_option('--no-auto-subscribe',
                  dest='auto_subscribe',
                  default=True,
                  action='store_false')
parser.add_option('--site',
                  dest='site',
                  default="https://app.humbughq.com",
                  action='store')
parser.add_option('--user',
                  dest='user',
                  default=os.environ["USER"],
                  action='store')
parser.add_option('--api-key-file',
                  dest='api_key_file',
                  default=os.path.join(os.environ["HOME"], "Private", ".humbug-api-key"),
                  action='store')
(options, args) = parser.parse_args()

api_key = file(options.api_key_file).read().strip()

sys.path.append(".")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import api.common
humbug_client = api.common.HumbugAPI(email=options.user + "@mit.edu",
                                     api_key=api_key,
                                     verbose=True,
                                     site=options.site)

start_time = time.time()

def humbug_username(zephyr_username):
    return zephyr_username.lower().split("@")[0] + "@mit.edu"

def send_humbug(zeph):
    if options.forward_class_messages:
        zeph["forged"] = "yes"
    zeph["sender"] = humbug_username(zeph["sender"])
    zeph['fullname']  = username_to_fullname(zeph['sender'])
    zeph['shortname'] = zeph['sender'].split('@')[0]
    if "subject" in zeph:
        zeph["subject"] = zeph["subject"][:60]
    if zeph['type'] == 'stream':
        # Forward messages sent to -c foo -i bar to stream bar subject "instance"
        if zeph["stream"] == "message":
            zeph['stream'] = zeph['subject']
            zeph['subject'] = "instance %s" % (zeph['stream'])
        elif zeph["stream"] == "tabbott-test5":
            zeph['stream'] = zeph['subject']
            zeph['subject'] = "test instance %s" % (zeph['stream'])

    for key in zeph.keys():
        if isinstance(zeph[key], unicode):
            zeph[key] = zeph[key].encode("utf-8")
        elif isinstance(zeph[key], str):
            zeph[key] = zeph[key].decode("utf-8")

    zeph['client'] = "zephyr_mirror"
    return humbug_client.send_message(zeph)

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

    domains = [
        ("@CS.CMU.EDU", " (CMU)"),
        ("@ANDREW.CMU.EDU", " (CMU)"),
        ("@IASTATE.EDU", " (IASTATE)"),
        ("@1TS.ORG", " (1TS)"),
        ("@DEMENTIA.ORG", " (DEMENTIA)"),
        ("@MIT.EDU", ""),
        ]
    for (domain, tag) in domains:
        if username.upper().endswith(domain):
            return username.split("@")[0] + tag
    return username

fullnames = {}
def username_to_fullname(username):
    if username not in fullnames:
        fullnames[username] = fetch_fullname(username)
    return fullnames[username]

current_zephyr_subs = {}
def ensure_subscribed(sub):
    if sub in current_zephyr_subs:
        return
    subs.add((sub, '*', '*'))
    current_zephyr_subs[sub] = True

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
    if os.stat(root_path + "/restart_stamp").st_mtime > start_time or \
            (options.user == "tabbott" and
             os.stat(root_path + "/tabbott_stamp").st_mtime > start_time):
        print
        print "%s: zephyr mirroring script has been updated; restarting..." % \
            (datetime.datetime.now())
        os.kill(child_pid, signal.SIGKILL)
        while True:
            try:
                os.execvp(root_path + "/zephyr_mirror.py", sys.argv)
            except:
                print "Error restarting, trying again."
                traceback.print_exc()
                time.sleep(10)

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
        continue

def process_notice(notice, log):
    try:
        zsig, body = notice.message.split("\x00", 1)
    except ValueError:
        body = notice.message
        zsig = ""
    is_personal = False
    is_huddle = False

    if notice.opcode == "PING":
        # skip PING messages
        return

    if isinstance(zsig, str):
        # Check for width unicode character u'\u200B'.encode("utf-8")
        if u'\u200B'.encode("utf-8") in zsig:
            print "%s: zephyr=>humbug: Skipping message from Humbug!" % \
                (datetime.datetime.now())
            return

    sender = notice.sender.lower().replace("athena.mit.edu", "mit.edu")
    recipient = notice.recipient.lower().replace("athena.mit.edu", "mit.edu")
    zephyr_class = notice.cls.lower()
    instance = notice.instance.lower()

    if (zephyr_class == "message" and recipient != ""):
        is_personal = True
        if body.startswith("CC:"):
            is_huddle = True
            # Map "CC: sipbtest espuser" => "starnine@mit.edu,espuser@mit.edu"
            huddle_recipients_list = [humbug_username(x.strip()) for x in
                                      body.split("\n")[0][4:].split()]
            if sender not in huddle_recipients_list:
                huddle_recipients_list.append(sender)
            huddle_recipients = ",".join(huddle_recipients_list)
    if (zephyr_class == "mail" and instance == "inbox"):
        is_personal = True

    # Drop messages not to the listed subscriptions
    if (zephyr_class not in current_zephyr_subs) and not \
            (is_personal and options.forward_personals):
        print "%s: zephyr=>humbug: Skipping ... %s/%s/%s" % \
            (datetime.datetime.now(), zephyr_class, instance, is_personal)
        return

    if is_huddle:
        zeph = { 'type'      : 'personal',
                 'time'      : str(notice.time),
                 'sender'    : sender,
                 'recipient' : huddle_recipients,
                 'zsig'      : zsig,  # logged here but not used by app
                 'content'   : body.split("\n", 1)[1] }
    elif is_personal:
        zeph = { 'type'      : 'personal',
                 'time'      : str(notice.time),
                 'sender'    : sender,
                 'recipient' : humbug_username(recipient),
                 'zsig'      : zsig,  # logged here but not used by app
                 'content'   : body }
    else:
        zeph = { 'type'      : 'stream',
                 'time'      : str(notice.time),
                 'sender'    : sender,
                 'stream'    : zephyr_class,
                 'subject'   : instance,
                 'zsig'      : zsig,  # logged here but not used by app
                 'content'   : body }

    # Add instances in for instanced personals
    if zeph['type'] == "personal" and instance != "personal":
        zeph["content"] = "[-i %s]" % (instance,) + "\n" + zeph["content"]

    print "%s: zephyr=>humbug: received a message on %s/%s from %s..." % \
        (datetime.datetime.now(), zephyr_class, instance, notice.sender)
    log.write(simplejson.dumps(zeph) + '\n')
    log.flush()

    res = send_humbug(zeph)
    if res.get("result") != "success":
        print >>sys.stderr, 'Error relaying zephyr'
        print zeph
        print res


def zephyr_to_humbug(options):
    import mit_subs_list
    if options.auto_subscribe:
        add_humbug_subscriptions()
    if options.forward_class_messages:
        for sub in mit_subs_list.all_subs:
            ensure_subscribed(sub)
        update_subscriptions_from_humbug()
    if options.forward_personals:
        subs.add(("message", "*", options.user + "@ATHENA.MIT.EDU"))
        if subscribed_to_mail_messages():
            subs.add(("mail", "inbox", options.user + "@ATHENA.MIT.EDU"))

    if options.resend_log:
        with open('zephyrs', 'r') as log:
            for ln in log:
                try:
                    zeph = simplejson.loads(ln)
                    print "%s: zephyr=>humbug: sending saved message to %s from %s..." % \
                        (datetime.datetime.now(), zeph.get('class', zeph.get('recipient')),
                         zeph['sender'])
                    send_humbug(zeph)
                except:
                    print >>sys.stderr, 'Could not send saved zephyr'
                    traceback.print_exc()
                    time.sleep(2)

    print "%s: zephyr=>humbug: Starting receive loop." % (datetime.datetime.now(),)

    if options.enable_log:
        log_file = "zephyrs"
    else:
        log_file = "/dev/null"

    with open(log_file, 'a') as log:
        process_loop(log)

def forward_to_zephyr(message):
    zsig = u"%s\u200B" % (username_to_fullname(message["sender_email"]))
    if ' dot ' in zsig:
        print "%s: humbug=>zephyr: ERROR!  Couldn't compute zsig for %s!" % \
            (datetime.datetime.now(), message["sender_email"])
        return

    wrapped_content = "\n".join("\n".join(textwrap.wrap(line))
            for line in message["content"].split("\n"))

    sender_email = message["sender_email"].replace("mit.edu", "ATHENA.MIT.EDU")
    print "%s: humbug=>zephyr: Forwarding message from %s" % \
        (datetime.datetime.now(), sender_email)
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
        zeph = zephyr.ZNotice(sender=sender_email, auth=True,
                              cls=zephyr_class, instance=instance)
        body = "%s\0%s" % (zsig, wrapped_content)
        zeph.setmessage(body)
        zeph.send()
    elif message['type'] == "personal":
        recipient = message["display_recipient"]["email"]
        recipient = recipient.replace("@mit.edu", "@ATHENA.MIT.EDU")
        zeph = zephyr.ZNotice(sender=sender_email,
                              auth=True, recipient=recipient,
                              cls="message", instance="personal")
        body = "%s\0%s" % (zsig, wrapped_content)
        zeph.setmessage(body)
        zeph.send()
    elif message['type'] == "huddle":
        cc_list = ["CC:"]
        cc_list.extend([user["email"].replace("@mit.edu", "")
                        for user in message["display_recipient"]])
        body = "%s\0%s\n%s" % (zsig, " ".join(cc_list), wrapped_content)
        for r in message["display_recipient"]:
            recipient = r["email"].replace("mit.edu", "ATHENA.MIT.EDU")
            zeph = zephyr.ZNotice(sender=sender_email, auth=True,
                                  recipient=recipient, cls="message",
                                  instance="personal")
            zeph.setmessage(body)
            zeph.send()

def maybe_forward_to_zephyr(message):
    if message["sender_email"] == options.user + "@mit.edu":
        timestamp_now = datetime.datetime.now().strftime("%s")
        if float(message["timestamp"]) < float(timestamp_now) - 15:
            print "%s humbug=>zephyr: Alert!  Out of order message: %s < %s" % \
                (datetime.datetime.now(), message["timestamp"], timestamp_now)
            return
        forward_to_zephyr(message)

def humbug_to_zephyr(options):
    # Sync messages from zephyr to humbug
    print "%s: humbug=>zephyr: Starting syncing messages." % (datetime.datetime.now(),)
    humbug_client.call_on_each_message(maybe_forward_to_zephyr,
                                       options={"mirror": 'zephyr_mirror'})

def subscribed_to_mail_messages():
    for (cls, instance, recipient) in parse_zephyr_subs(verbose=False):
        if (cls.lower() == "mail" and instance.lower() == "inbox"):
            return True
    return False

def add_humbug_subscriptions():
    zephyr_subscriptions = set()
    for (cls, instance, recipient) in parse_zephyr_subs(verbose=options.verbose):
        if cls == "message" and recipient == "*":
            if instance == "*":
                continue
            # If you're on -i white-magic on zephyr, get on stream white-magic on humbug
            # instead of subscribing to stream message
            zephyr_subscriptions.add(instance)
            continue
        elif instance != "*" or recipient != "*":
            if options.verbose:
                print "Skipping ~/.zephyr.subs line: [%s,%s,%s]: Non-* values" % \
                    (cls, instance, recipient)
            continue
        zephyr_subscriptions.add(cls)
    if len(zephyr_subscriptions) != 0:
        humbug_client.subscribe(list(zephyr_subscriptions))

def parse_zephyr_subs(verbose=False):
    if verbose:
        print "Adding your ~/.zephyr.subs subscriptions to Humbug!"
    zephyr_subscriptions = set()
    subs_file = os.path.join(os.environ["HOME"], ".zephyr.subs")
    if not os.path.exists(subs_file):
        if verbose:
            print >>sys.stderr, "Couldn't find .zephyr.subs!"
            print >>sys.stderr, "Do you mean to run with --no-auto-subscribe?"
        return []

    for line in file(subs_file, "r").readlines():
        line = line.strip()
        if len(line) == 0:
            continue
        try:
            (cls, instance, recipient) = line.split(",")
        except:
            if verbose:
                print >>sys.stderr, "Couldn't parse ~/.zephyr.subs line: [%s]" % (line,)
            continue
        zephyr_subscriptions.add((cls.strip(), instance.strip(), recipient.strip()))
    return zephyr_subscriptions

if options.forward_from_humbug:
    print "This option is obsolete."
    sys.exit(0)

child_pid = os.fork()
if child_pid == 0:
    # Run the humbug => zephyr mirror in the child
    import zephyr
    zephyr.init()
    humbug_to_zephyr(options)
    sys.exit(0)

import zephyr
zephyr.init()
subs = zephyr.Subscriptions()
zephyr_to_humbug(options)
