#!/usr/bin/python

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
    browser.addheaders.append(('X-CSRFToken', csrf_token))
    zephyr_data = urllib.urlencode(zeph.items())
    browser.open("https://app.humbughq.com/forge_zephyr/", zephyr_data)

subs_list = """\
""".split()

if __name__ == '__main__':
    import mechanize
    import urllib
    import cgi
    import sys
    import logging
    import zephyr
    import BeautifulSoup
    import traceback
    import simplejson

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
            notice = zephyr.receive(block=True)
            zsig, body = notice.message.split("\x00", 1)

            lines = body.split('\n')
            newbody = ""
            for i in range(0, len(lines)):
                if (i + 1 == len(lines) or
                    lines[i].strip() == '' or
                    lines[i+1].strip() == ''):
                    newbody += lines[i] + "\n"
                else:
                    newbody += lines[i] + " "

            if notice.cls not in subs_list:
                continue
            zeph = { 'type'      : 'class',
                     'time'      : str(notice.time),
                     'sender'    : notice.sender,
                     'class'     : notice.cls,
                     'instance'  : notice.instance,
                     'zsig'      : zsig,  # logged here but not used by app
                     'new_zephyr': newbody }
            for k,v in zeph.items():
                zeph[k] = cgi.escape(v)

            log.write(simplejson.dumps(zeph) + '\n')
            log.flush()

            print "received a message on %s from %s..." % (zeph['class'], zeph['sender'])
            send_zephyr(zeph)
            print "forwarded"
