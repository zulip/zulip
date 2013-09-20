#!/usr/bin/env python
# coding=utf-8

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

if len(sys.argv) == 2:
	template_name = sys.argv[1]

template = open("templates/%s.txt" % template_name).read()

def get_message(template, first_name):
	message = "\n".join(template.strip().split("\n")[2:])
	return message.replace("{{name}}", first_name)

def get_subject(template):
	return template.split("\n")[0].strip()

send_count = 0
for person in people_list:
	fields = person.split('\t')
	name,email = fields[:2] #,realm,last_send,send_count,last_pointer,pointer_count,last_updates = fields
	first_name = name.split()[0]
	print first_name,name,email, '-', send_count

	msg = MIMEText(get_message(template, first_name))
	msg['Subject'] = get_subject(template)
	msg['From'] = 'Waseem Daher <wdaher@zulip.com>'
	msg['To'] = '%s <%s>' % (name,email,)
	server.append("[Gmail]/Drafts",
				 '',
				 imaplib.Time2Internaldate(time.time()),
				 str(msg))

server.logout()