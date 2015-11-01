from __future__ import print_function
# This is hacky code to analyze data on our support stream.  The main
# reusable bits are get_recent_messages and get_words.

import zulip
import re
import collections

def get_recent_messages(client, narrow, count=100):
    narrow = [word.split(':') for word in narrow.split()]
    req = {
        'narrow': narrow,
        'num_before': count,
        'num_after': 0,
        'anchor': 1000000000,
        'apply_markdown': False
    }
    old_messages = client.do_api_query(req, zulip.API_VERSTRING + 'messages', method='GET')
    if 'messages' not in old_messages:
        return []
    return old_messages['messages']

def get_words(content):
    regex = "[A-Z]{2,}(?![a-z])|[A-Z][a-z]+(?=[A-Z])|[\'\w\-]+"
    words = re.findall(regex, content, re.M)
    words = [w.lower() for w in words]
    # words = [w.rstrip('s') for w in words]
    return words

def analyze_messages(msgs, word_count, email_count):
    for msg in msgs:
        if False:
            if ' ack' in msg['content']:
                name = msg['sender_full_name'].split()[0]
                print('ACK', name)
        m = re.search('ticket (Z....).*email: (\S+).*~~~(.*)', msg['content'], re.M | re.S)
        if m:
            ticket, email, req = m.groups()
            words = get_words(req)
            for word in words:
                word_count[word] += 1
            email_count[email] += 1
        if False:
            print()
            for k, v in msg.items():
                print('%-20s: %s' % (k, v))

def generate_support_stats():
    client = zulip.Client()
    narrow = 'stream:support'
    count = 2000
    msgs = get_recent_messages(client, narrow, count)
    msgs_by_topic = collections.defaultdict(list)
    for msg in msgs:
        topic = msg['subject']
        msgs_by_topic[topic].append(msg)

    word_count = collections.defaultdict(int)
    email_count = collections.defaultdict(int)

    if False:
        for topic in msgs_by_topic:
            msgs = msgs_by_topic[topic]
    analyze_messages(msgs, word_count, email_count)

    if True:
        words = word_count.keys()
        words = [w for w in words if word_count[w] >= 10]
        words = [w for w in words if len(w) >= 5]
        words = sorted(words, key=lambda w: word_count[w], reverse=True)
        for word in words:
            print(word, word_count[word])

    if False:
        emails = email_count.keys()
        emails = sorted(emails, key=lambda w: email_count[w], reverse=True)
        for email in emails:
            print(email, email_count[email])

generate_support_stats()
