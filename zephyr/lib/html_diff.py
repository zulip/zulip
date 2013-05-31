import difflib
import platform
import logging

# TODO: handle changes in link hrefs

def highlight_with_class(klass, text):
    return '<span class="%s">%s</span>' % (klass, text)

def highlight_inserted(text):
    return highlight_with_class('highlight_text_inserted', text)

def highlight_deleted(text):
    return highlight_with_class('highlight_text_deleted', text)

def highlight_replaced(text):
    return highlight_with_class('highlight_text_replaced', text)

def chunkize(text, in_tag):
    start = 0
    idx = 0
    chunks = []
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
    retval = ''
    for type, text in chunks:
        if type == 'text':
            retval += highlight_func(text)
        else:
            retval += text
    return retval

def verify_html(html):
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
    sm = difflib.SequenceMatcher(lambda c: c in " \t\v\n", s1, s2, autojunk=False)
    retval = ''
    in_tag = False

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'replace':
            chunks, in_tag = chunkize(s2[j1:j2], in_tag)
            retval += highlight_chunks(chunks, highlight_replaced)
        elif op == 'delete':
            retval += highlight_deleted('&nbsp;')
        elif op == 'insert':
            chunks, in_tag = chunkize(s2[j1:j2], in_tag)
            retval += highlight_chunks(chunks, highlight_inserted)
        elif op == 'equal':
            chunks, in_tag = chunkize(s2[j1:j2], in_tag)
            retval += s2[j1:j2]

    if not verify_html(retval):
        from zephyr.lib.actions import internal_send_message
        # We probably want more information here
        logging.getLogger('').error('HTML diff produced mal-formed HTML')

        subject = "HTML diff failure on %s" % (platform.node(),)
        internal_send_message("humbug+errors@humbughq.com", "stream",
                              "errors", subject, "HTML diff produced malformed HTML")
        return s2

    return retval

