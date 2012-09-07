#!/usr/bin/python
import mechanize
import urllib
import cgi
import sys
import logging
import zephyr
import BeautifulSoup

logger = logging.getLogger("mechanize")
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

browser = mechanize.Browser()
csrf_token = None

def browser_login():
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

# example: send_zephyr("Verona", "Auto2", "test")
def send_zephyr(sender, klass, instance, content):
    browser.addheaders.append(('X-CSRFToken', csrf_token))
    zephyr_data = urllib.urlencode([('type', 'class'), ('class', klass), ('sender', sender),
                                    ('instance', instance), ('new_zephyr', content)])
    browser.open("https://app.humbughq.com/forge_zephyr/", zephyr_data)

browser_login()

subs_list = """\
"""

subs = zephyr.Subscriptions()
for sub in subs_list.split():
    subs.add((sub, '*', '*'))

print "Starting receive loop"
while True:
    notice = zephyr.receive(block=True)
    zsig, body = notice.message.split("\x00", 1)
    print "received a message on %s from %s..." % (notice.cls, notice.sender) ,
    send_zephyr(cgi.escape(notice.sender), cgi.escape(notice.cls), cgi.escape(notice.instance), cgi.escape(body))
    print "forwarded"
