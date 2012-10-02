#!/usr/bin/python
import mechanize
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
from urllib2 import HTTPError

sys.path.append("/mit/tabbott/Public/python-zephyr/")
sys.path.append("/mit/tabbott/Public/python-zephyr/build/lib.linux-x86_64-2.6/")

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
                  dest='forward_to_humbug',
                  default=True,
                  action='store_false')
parser.add_option('--site',
                  dest='site',
                  default="https://app.humbughq.com",
                  action='store')
parser.add_option('--api-key',
                  dest='api_key',
                  default="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                  action='store')
(options, args) = parser.parse_args()

sys.path.append(".")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import api.common
humbug_client = api.common.HumbugAPI(email=os.environ["USER"] + "@mit.edu",
                                     api_key=options.api_key,
                                     verbose=True,
                                     site=options.site)

import zephyr
zephyr.init()

browser = None
csrf_token = None

def browser_login():
    logger = logging.getLogger("mechanize")
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.INFO)

    global browser
    browser = mechanize.Browser()
    browser.set_handle_robots(False)
    ## debugging code to consider
    # browser.set_debug_http(True)
    # browser.set_debug_responses(True)
    # browser.set_debug_redirects(True)
    # browser.set_handle_refresh(False)

    browser.add_password("https://app.humbughq.com/", "tabbott", "xxxxxxxxxxxxxxxxx", "wiki")
    browser.open("https://app.humbughq.com/")
    browser.follow_link(text_regex="\s*Log in\s*")
    browser.select_form(nr=0)
    browser["username"] = os.environ["USER"] + "@mit.edu"
    browser["password"] = os.environ["USER"]

    global csrf_token
    csrf_token = browser["csrfmiddlewaretoken"]

    browser.submit()

def compute_humbug_username(zephyr_username):
    return zephyr_username.lower().split("@")[0] + "@mit.edu"

def send_humbug(zeph):
    zeph["sender"] = compute_humbug_username(zeph["sender"])
    if "recipient" in zeph:
        zeph["recipient"] = compute_humbug_username(zeph["recipient"])
    zeph['fullname']  = username_to_fullname(zeph['sender'])
    zeph['shortname'] = zeph['sender'].split('@')[0]
    if "instance" in zeph:
        zeph["instance"] = zeph["instance"][:30]
    browser.addheaders.append(('X-CSRFToken', csrf_token))

    humbug_data = []
    for key in zeph.keys():
        if key == "zsig":
            # Don't send zsigs to the Humbug server
            continue
        if isinstance(zeph[key], unicode):
            val = zeph[key].encode("utf-8")
        elif isinstance(zeph[key], str):
            val = zeph[key].decode("utf-8")
        humbug_data.append((key, val))

    try:
        browser.open("https://app.humbughq.com/forge_message/", urllib.urlencode(humbug_data))
    except HTTPError, e:
        if e.code == 401:
            # Digest auth failed; server was probably restarted; login in again
            while True:
                try:
                    browser_login()
                except HTTPError, e:
                    print "Failed logging in; trying again in 10 seconds."
                    time.sleep(10)
                    continue
                break

            print "Auth failure; trying again after logging in a second time!"
            browser.open("https://app.humbughq.com/forge_message/", urllib.urlencode(humbug_data))
        else:
            raise


def fetch_fullname(username):
    try:
        match_user = re.match(r'([a-zA-Z0-9_]+)@mit\.edu', username)
        if match_user:
            proc = subprocess.Popen(['hesinfo', match_user.group(1), 'passwd'], stdout=subprocess.PIPE)
            out, _err_unused = proc.communicate()
            if proc.returncode == 0:
                return out.split(':')[4].split(',')[0]
    except:
        print >>sys.stderr, 'Error getting fullname for', username
        traceback.print_exc()

    return username.title().replace('@', ' at ').replace('.', ' dot ')

fullnames = {}
def username_to_fullname(username):
    if username not in fullnames:
        fullnames[username] = fetch_fullname(username)
    return fullnames[username]


def process_loop(log):
    import mit_subs_list
    while True:
        try:
            notice = zephyr.receive(block=True)
            zsig, body = notice.message.split("\x00", 1)
            is_personal = False
            is_huddle = False
            if isinstance(zsig, str):
                # Check for width unicode character u'\u200B'.encode("utf-8")
                if u'\u200B'.encode("utf-8") in zsig:
                    print "Skipping message from Humbug!"
                    continue

            sender = notice.sender.lower().replace("athena.mit.edu", "mit.edu")
            recipient = notice.recipient.lower().replace("athena.mit.edu", "mit.edu")

            if (notice.cls.lower() == "message" and
                notice.instance.lower() == "personal"):
                is_personal = True
                if body.startswith("CC:"):
                    is_huddle = True
                    # Map "CC: sipbtest espuser" => "starnine@mit.edu,espuser@mit.edu"
                    huddle_recipients_list = [x + "@mit.edu" for x in
                                              body.split("\n")[0][4:].split()]
                    if sender not in huddle_recipients_list:
                        huddle_recipients_list.append(sender)
                    huddle_recipients = ",".join(huddle_recipients_list)

            if notice.opcode != "":
                # skip PING messages
                continue

            # Drop messages not to the listed subscriptions
            if (notice.cls.lower() not in mit_subs_list.all_subs) and not \
                    (is_personal and options.forward_personals):
                print "Skipping ...", notice.cls, notice.instance, is_personal
                continue

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
                         'recipient' : recipient,
                         'zsig'      : zsig,  # logged here but not used by app
                         'content'   : body }
            else:
                zeph = { 'type'      : 'class',
                         'time'      : str(notice.time),
                         'sender'    : sender,
                         'class'     : notice.cls.lower(),
                         'instance'  : notice.instance,
                         'zsig'      : zsig,  # logged here but not used by app
                         'content'   :body }

            log.write(simplejson.dumps(zeph) + '\n')
            log.flush()

            print "%s: received a message on %s/%s from %s..." % \
                (datetime.datetime.now(), notice.cls, notice.instance, notice.sender)
            send_humbug(zeph)
        except:
            print >>sys.stderr, 'Error relaying zephyr'
            traceback.print_exc()
            time.sleep(2)


def zephyr_to_humbug(options):
    browser_login()

    import mit_subs_list
    subs = zephyr.Subscriptions()
    if options.forward_class_messages:
        for sub in mit_subs_list.all_subs:
            subs.add((sub, '*', '*'))
    if options.forward_personals:
        subs.add(("message", "personal", "*"))

    if options.resend_log:
        with open('zephyrs', 'r') as log:
            for ln in log:
                try:
                    zeph = simplejson.loads(ln)
                    print "sending saved message to %s from %s..." % \
                        (zeph.get('class', zeph.get('recipient')), zeph['sender'])
                    send_humbug(zeph)
                except:
                    print >>sys.stderr, 'Could not send saved zephyr'
                    traceback.print_exc()
                    time.sleep(2)

    print "Starting receive loop"

    if options.enable_log:
        log_file = "zephyrs"
    else:
        log_file = "/dev/null"

    with open(log_file, 'a') as log:
        process_loop(log)

def forward_to_zephyr(message):
    zsig = u"%s\u200B" % (username_to_fullname(message["sender_email"]))
    if ' dot ' in zsig:
        print "ERROR!  Couldn't compute zsig for %s!" % (message["sender_email"])
        return

    content = message["content"]
    cleaned_content = content.replace('&lt;','<').replace('&gt;','>').replace('&amp;', '&')
    wrapped_content = "\n".join("\n".join(textwrap.wrap(line))
            for line in cleaned_content.split("\n"))

    print "Sending message from %s humbug=>zephyr at %s" % (message["sender_email"], datetime.datetime.now())
    if message['type'] == "class":
        zeph = zephyr.ZNotice(sender=message["sender_email"].replace("mit.edu", "ATHENA.MIT.EDU"),
                              auth=True, cls=message["display_recipient"],
                              instance=message["instance"])
        body = "%s\0%s" % (zsig, wrapped_content)
        zeph.setmessage(body)
        zeph.send()
    elif message['type'] == "personal":
        zeph = zephyr.ZNotice(sender=message["sender_email"].replace("mit.edu", "ATHENA.MIT.EDU"),
                              auth=True, recipient=message["display_recipient"].replace("mit.edu", "ATHENA.MIT.EDU"),
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
            zeph = zephyr.ZNotice(sender=message["sender_email"].replace("mit.edu", "ATHENA.MIT.EDU"),
                                  auth=True, recipient=r["email"].replace("mit.edu", "ATHENA.MIT.EDU"),
                                  cls="message", instance="personal")
            zeph.setmessage(body)
            zeph.send()

def maybe_forward_to_zephyr(message):
    if message["sender_email"] == os.environ["USER"] + "@mit.edu":
        if float(message["timestamp"]) < float(datetime.datetime.now().strftime("%s")) - 5:
            print "Alert!  Out of order message!", message["timestamp"], datetime.datetime.now().strftime("%s")
            return
        forward_to_zephyr(message)

def humbug_to_zephyr(options):
    # Sync messages from zephyr to humbug
    print "Starting syncing messages."
    humbug_client.call_on_each_message(maybe_forward_to_zephyr,
                                       options={"mit_sync_bot": 'yes'})

if options.forward_to_humbug:
    zephyr_to_humbug(options)
else:
    humbug_to_zephyr(options)
