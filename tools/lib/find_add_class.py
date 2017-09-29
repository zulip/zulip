
from typing import List, Set, Tuple

import os
import re

GENERIC_KEYWORDS = [
    'active',
    'alert',
    'danger',
    'condensed',
    'disabled',
    'error',
    'expanded',
    'fade-out',
    'first',
    'hide',
    'in',
    'show',
    'notdisplayed',
    'popover',
    'no-border',
    'second',
    'selected',
    'slide-left',
    'success',
    'text-error',
    'warning',
    'zoom-in',  # TODO: clean these up, they are confusing
    'zoom-out',
]

def raise_error(fn, i, line):
    # type: (str, int, str) -> None
    error = '''
        In %s line %d there is the following line of code:

        %s

        Our tools want to be able to identify which modules
        add which HTML/CSS classes, and we need two things to
        happen:

            - The code must explicitly name the class.
            - Only one module can refer to that class (unless
              it is something generic like an alert class).

        If you get this error, you can usually address it by
        refactoring your code to be more explicit, or you can
        move the common code that sets the class to a library
        module.  If neither of those applies, you need to
        modify %s
        ''' % (fn, i, line, __file__)
    raise Exception(error)

def generic(html_class):
    # type: (str) -> bool
    for kw in GENERIC_KEYWORDS:
        if kw in html_class:
            return True
    return False

def display(fns):
    # type: (List[str]) -> None
    for tup in find(fns):
        # this format is for code generation purposes
        print(' ' * 8 + repr(tup) + ',')

def find(fns):
    # type: (List[str]) -> List[Tuple[str, str]]
    encountered = set()  # type: Set[str]
    tups = []  # type: List[Tuple[str, str]]
    for full_fn in fns:
        # Don't check frontend tests, since they may do all sorts of
        # extra hackery that isn't of interest to us.
        if full_fn.startswith("frontend_tests"):
            continue
        lines = list(open(full_fn))
        fn = os.path.basename(full_fn)
        module_classes = set()  # type: Set[str]
        for i, line in enumerate(lines):
            if 'addClass' in line:
                html_classes = []  # type: List[str]
                m = re.search('addClass\([\'"](.*?)[\'"]', line)
                if m:
                    html_classes = [m.group(1)]
                if not html_classes:
                    if 'bar-success' in line:
                        html_classes = ['bar-success', 'bar-danger']
                    elif fn == 'hotspots.js' and 'arrow_placement' in line:
                        html_classes = ['arrow-top', 'arrow-left', 'arrow-bottom', 'arrow-right']
                    elif 'color_class' in line:
                        continue
                    elif 'stream_dark' in line:
                        continue
                    elif fn == 'signup.js' and 'class_to_add' in line:
                        html_classes = ['error', 'success']
                    elif fn == 'ui_report.js' and 'status_classes' in line:
                        html_classes = ['alert']

                if not html_classes:
                    raise_error(full_fn, i, line)
                for html_class in html_classes:
                    if generic(html_class):
                        continue
                    if html_class in module_classes:
                        continue
                    if html_class in encountered:
                        raise_error(full_fn, i, line)
                    tups.append((fn, html_class))
                    module_classes.add(html_class)
                    encountered.add(html_class)
    return tups
