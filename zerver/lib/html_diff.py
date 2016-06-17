from __future__ import absolute_import

from six import text_type
from typing import Callable, Tuple

from django.conf import settings

from diff_match_patch import diff_match_patch
import platform
import logging

# TODO: handle changes in link hrefs

def highlight_with_class(klass, text):
    # type: (text_type, text_type) -> text_type
    return '<span class="%s">%s</span>' % (klass, text)

def highlight_inserted(text):
    # type: (text_type) -> text_type
    return highlight_with_class('highlight_text_inserted', text)

def highlight_deleted(text):
    # type: (text_type) -> text_type
    return highlight_with_class('highlight_text_deleted', text)

def highlight_replaced(text):
    # type: (text_type) -> text_type
    return highlight_with_class('highlight_text_replaced', text)

def chunkize(text, in_tag):
    # type: (text_type, bool) -> Tuple[List[Tuple[text_type, text_type]], bool]
    start = 0
    idx = 0
    chunks = [] # type: List[Tuple[text_type, text_type]]
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
    # type: (List[Tuple[text_type, text_type]], Callable[[text_type], text_type]) -> text_type
    retval = u''
    for type, text in chunks:
        if type == 'text':
            retval += highlight_func(text)
        else:
            retval += text
    return retval

def verify_html(html):
    # type: (text_type) -> bool
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

def highlight_html_differences(s1, s2):
    # type: (text_type, text_type) -> text_type
    differ = diff_match_patch()
    ops = differ.diff_main(s1, s2)
    differ.diff_cleanupSemantic(ops)
    retval = u''
    in_tag = False

    idx = 0
    while idx < len(ops):
        op, text = ops[idx]
        next_op = None
        if idx != len(ops) - 1:
            next_op, next_text = ops[idx + 1]
        if op == diff_match_patch.DIFF_DELETE and next_op == diff_match_patch.DIFF_INSERT:
            # Replace operation
            chunks, in_tag = chunkize(next_text, in_tag)
            retval += highlight_chunks(chunks, highlight_replaced)
            idx += 1
        elif op == diff_match_patch.DIFF_INSERT and next_op == diff_match_patch.DIFF_DELETE:
            # Replace operation
            # I have no idea whether diff_match_patch generates inserts followed
            # by deletes, but it doesn't hurt to handle them
            chunks, in_tag = chunkize(text, in_tag)
            retval += highlight_chunks(chunks, highlight_replaced)
            idx += 1
        elif op == diff_match_patch.DIFF_DELETE:
            retval += highlight_deleted('&nbsp;')
        elif op == diff_match_patch.DIFF_INSERT:
            chunks, in_tag = chunkize(text, in_tag)
            retval += highlight_chunks(chunks, highlight_inserted)
        elif op == diff_match_patch.DIFF_EQUAL:
            chunks, in_tag = chunkize(text, in_tag)
            retval += text
        idx += 1

    if not verify_html(retval):
        from zerver.lib.actions import internal_send_message
        # We probably want more information here
        logging.getLogger('').error('HTML diff produced mal-formed HTML')

        if settings.ERROR_BOT is not None:
            subject = "HTML diff failure on %s" % (platform.node(),)
            internal_send_message(settings.ERROR_BOT, "stream",
                                  "errors", subject, "HTML diff produced malformed HTML")
        return s2

    return retval

