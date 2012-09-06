#!/usr/bin/python
import mechanize
import re
import urllib

import sys, logging
logger = logging.getLogger("mechanize")
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

def browser_login(br):
    br.set_handle_robots(False)
    ## debugging code to consider
    # br.set_debug_http(True)
    # br.set_debug_responses(True)
    # br.set_debug_redirects(True)
    # br.set_handle_refresh(False)
    br.add_password("https://app.humbughq.com/", "tabbott", "xxxxxxxxxxxxxxxxx", "wiki")
    login_info = urllib.urlencode([('username', 'iago'), ('password', 'iago')])
    response = br.open("https://app.humbughq.com/")
    br.follow_link(text_regex="\s*Log in\s*")
    br.select_form(nr=0)
    br["username"] = "iago"
    br["password"] = "iago"
    response2 = br.submit()
    # This is a horrible horrible hack
    data = "".join(response2.readlines())
    val = data.index("csrfmiddlewaretoken")
    csrf = data[val+28:val+60]
    return csrf

# example: send_zephyr("Verona", "Auto2", "test")
def send_zephyr(sender, klass, instance, content):
    br = mechanize.Browser()
    hack_content = "Message from MIT Zephyr sender %s\n" % (sender,) + content
    csrf = browser_login(br)
    br.addheaders.append(('X-CSRFToken', csrf))
    zephyr_data = urllib.urlencode([('type', 'class'), ('class', klass),
                                    ('instance', instance), ('new_zephyr', hack_content)])
    br.open("https://app.humbughq.com/zephyr/", zephyr_data)

import zephyr
subs = zephyr.Subscriptions()
subs.add(('tabbott-test2', '*', '*'))

while True:
    notice = zephyr.receive(block=True)
    [zsig, body] = notice.message.split("\x00")
    send_zephyr(notice.sender, notice.cls, notice.instance, body)
