#!/usr/bin/python
import mechanize
import urllib
import cgi
import sys
import logging
import zephyr
import BeautifulSoup
import traceback
import simplejson
import re
import time
import subprocess

from mit_subs_list import subs_list

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
    browser["username"] = "iago"
    browser["password"] = "iago"

    global csrf_token
    soup = BeautifulSoup.BeautifulSoup(browser.submit().read())
    csrf_token = soup.find('input', attrs={'name': 'csrfmiddlewaretoken'})['value']

def send_zephyr(zeph):
    zeph['fullname']  = cgi.escape(username_to_fullname(zeph['sender']))
    zeph['shortname'] = cgi.escape(zeph['sender'].split('@')[0])

    browser.addheaders.append(('X-CSRFToken', csrf_token))
    zephyr_data = urllib.urlencode([(k, v.encode('utf-8')) for k,v in zeph.items()])
    browser.open("https://app.humbughq.com/forge_zephyr/", zephyr_data)

def unwrap_lines(body):
    return '\n'.join(p.replace('\n', ' ') for p in re.split(r'\n[ \t\n]', body))

def fetch_fullname(username):
    try:
        match_user = re.match(r'([a-zA-Z0-9_]+)@ATHENA\.MIT\.EDU', username)
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

browser_login()

subs = zephyr.Subscriptions()
for sub in subs_list:
    subs.add((sub, '*', '*'))

if sys.argv[1:] == ['--resend-log']:
    try:
        with open('zephyrs', 'r') as log:
            for ln in log:
                zeph = simplejson.loads(ln)
                print "sending saved message to %s from %s..." % (zeph['class'], zeph['sender'])
                send_zephyr(zeph)
    except:
        print >>sys.stderr, 'Could not load zephyr log'
        traceback.print_exc()

with open('zephyrs', 'a') as log:
    print "Starting receive loop"
    while True:
        try:
            notice = zephyr.receive(block=True)
            zsig, body = notice.message.split("\x00", 1)

            if notice.cls not in subs_list:
                continue
            zeph = { 'type'      : 'class',
                     'time'      : str(notice.time),
                     'sender'    : notice.sender,
                     'class'     : notice.cls,
                     'instance'  : notice.instance,
                     'zsig'      : zsig,  # logged here but not used by app
                     'new_zephyr': unwrap_lines(body) }
            for k,v in zeph.items():
                zeph[k] = cgi.escape(v)

            log.write(simplejson.dumps(zeph) + '\n')
            log.flush()

            print "received a message on %s from %s..." % (zeph['class'], zeph['sender'])
            send_zephyr(zeph)
            print "forwarded"
        except:
            print >>sys.stderr, 'Error relaying zephyr'
            traceback.print_exc()
            time.sleep(2)
