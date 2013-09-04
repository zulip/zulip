#!/usr/bin/env python

import sys
import time
import os.path
from email.mime.text import MIMEText
import imaplib

email_config = {}
email_config_lines = open(os.path.expanduser("~/.msmtprc")).read().strip().split("\n")
for line in email_config_lines:
	k,v = line.split()
	email_config[k] = v

USERNAME = email_config['user']
PASSWORD = email_config['password']

people = """
"""


########################################
people_list = people.strip().split('\n')

server = imaplib.IMAP4_SSL('imap.gmail.com')
server.login(USERNAME, PASSWORD)

for person in people_list:
	fields = person.split('\t')
	name,email,realm,last_send,send_count,last_pointer,pointer_count,last_updates = fields
	first_name = name.split()[0]
	print first_name,name,email, '-', send_count

	msg = MIMEText("""Hi %s,

Welcome to Zulip!

https://zulip.com/hello has a nice overview of what it is we're up to, but here are a couple tips that'll help you get the most out of it:

1. Zulip works best when it's always open, so grab our apps! (Mac, Windows, Linux, Android, iOS)
   https://zulip.com/apps

2. Keyboard shortcuts: learn about them in the Keyboard Shortcuts tab under the gear icon. (Or press '?')

3. Talking about code? Use our Markdown support to format and even syntax-highlight your messages!

For example, the following will get nice highlighting:
~~~ .py
def fn(arg):
    print "Hello"
~~~

4. Got automation? Check out https://zulip.com/integrations and https://zulip.com/api for easy integration with services like GitHub, Jenkins, Nagios, and Trac. They're super-easy to set up and make things a lot more useful.

5. Emoji. Because :ramen:

Zulip is under active development, and we have a team of engineers standing by to respond to your feedback, so please report bugs and let us know what you think! There's a feedback tab under the gear icon in the upper-right corner, or you can e-mail us at feedback@zulip.com.

-Waseem, for the Zulip team
""".strip() % (first_name,))
	msg['Subject'] = 'Welcome to Zulip!'
	msg['From'] = 'Waseem Daher <wdaher@zulip.com>'
	msg['To'] = '%s <%s>' % (name,email,)
	server.append("[Gmail]/Drafts",
				 '',
				 imaplib.Time2Internaldate(time.time()),
				 str(msg))

server.logout()