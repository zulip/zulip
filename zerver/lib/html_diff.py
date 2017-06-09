from __future__ import absolute_import

from typing import Callable, List, Tuple, Text

from django.conf import settings

from diff_match_patch import diff_match_patch
import platform
import logging

# TODO: handle changes in link hrefs

def highlight_with_class(klass, text):
    # type: (Text, Text) -> Text
    return '<span class="%s">%s</span>' % (klass, text)

def highlight_inserted(text):
    # type: (Text) -> Text
    return highlight_with_class('highlight_text_inserted', text)

def highlight_deleted(text):
    # type: (Text) -> Text
    return highlight_with_class('highlight_text_deleted', text)

def chunkize(text, in_tag):
    # type: (Text, bool) -> Tuple[List[Tuple[Text, Text]], bool]
    start = 0
    idx = 0
    chunks = []  # type: List[Tuple[Text, Text]]
    for c in text:
        if c == '<':
            in_tag = True
            if start != idx:
                chunks.append(('text', text[start:idx]))
            start = idx
        elif c == '>':
            in_tag = False
            if start != idx + 1:
                chunks.append(('tag', text[start:idx + 1]))
            start = idx + 1
        idx += 1

    if start != idx:
        chunks.append(('tag' if in_tag else 'text', text[start:idx]))
    return chunks, in_tag

def highlight_chunks(chunks, highlight_func):
    # type: (List[Tuple[Text, Text]], Callable[[Text], Text]) -> Text
    retval = u''
    for type, text in chunks:
        if type == 'text':
            retval += highlight_func(text)
        else:
            retval += text
    return retval

def verify_html(html):
    # type: (Text) -> bool
    # TODO: Actually parse the resulting HTML to ensure we don't
    # create mal-formed markup.  This is unfortunately hard because
    # we both want pretty strict parsing and we want to parse html5
    # fragments.  For now, we do a basic sanity check.
    in_tag = False
    for c in html:
        if c == '<':
            if in_tag:
                return False
            in_tag = True
        elif c == '>':
            if not in_tag:
                return False
            in_tag = False
    if in_tag:
        return False
    return True

def check_tags(text):
    # type: (Text) -> Text
    # The current diffing algorithm produces malformed html when text is
    # added to existing new lines. This patch manually corrects that.
    in_tag = False
    if text.endswith('<'):
        text = text[:-1]
    for c in text:
        if c == '<':
            in_tag = True
        elif c == '>' and not in_tag:
            text = '<' + text
            break
    return text

def highlight_html_differences(s1, s2):
    # type: (Text, Text) -> Text
    differ = diff_match_patch()
    ops = differ.diff_main(s1, s2)
    differ.diff_cleanupSemantic(ops)
    retval = u''
    in_tag = False

    idx = 0
    while idx < len(ops):
        op, text = ops[idx]
        text = check_tags(text)
        if idx != 0:
            prev_op, prev_text = ops[idx - 1]
            prev_text = check_tags(prev_text)
            # Remove visual offset from editing newlines
            if '<p><br>' in text:
                text = text.replace('<p><br>', '<p>')
            elif prev_text.endswith('<p>') and text.startswith('<br>'):
                text = text[4:]
        if op == diff_match_patch.DIFF_DELETE:
            chunks, in_tag = chunkize(text, in_tag)
            retval += highlight_chunks(chunks, highlight_deleted)
        elif op == diff_match_patch.DIFF_INSERT:
            chunks, in_tag = chunkize(text, in_tag)
            retval += highlight_chunks(chunks, highlight_inserted)
        elif op == diff_match_patch.DIFF_EQUAL:
            chunks, in_tag = chunkize(text, in_tag)
            retval += text
        idx += 1

    if not verify_html(retval):
        from zerver.lib.actions import internal_send_message
        from zerver.models import get_system_bot
        # We probably want more information here
        logging.getLogger('').error('HTML diff produced mal-formed HTML')

        if settings.ERROR_BOT is not None:
            subject = "HTML diff failure on %s" % (platform.node(),)
            realm = get_system_bot(settings.ERROR_BOT).realm
            internal_send_message(realm, settings.ERROR_BOT, "stream",
                                  "errors", subject, "HTML diff produced malformed HTML")
        return s2

    return retval
