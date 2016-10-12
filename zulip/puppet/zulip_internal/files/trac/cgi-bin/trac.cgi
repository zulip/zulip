#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2009 Edgewall Software
# Copyright (C) 2003-2004 Jonas Borgström <jonas@edgewall.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Jonas Borgström <jonas@edgewall.com>

try:
    import os
    import pkg_resources
    if 'TRAC_ENV' not in os.environ and \
       'TRAC_ENV_PARENT_DIR' not in os.environ:
        os.environ['TRAC_ENV'] = '/home/zulip/trac'
    if 'PYTHON_EGG_CACHE' not in os.environ:
        if 'TRAC_ENV' in os.environ:
            egg_cache = os.path.join(os.environ['TRAC_ENV'], '.egg-cache')
        elif 'TRAC_ENV_PARENT_DIR' in os.environ:
            egg_cache = os.path.join(os.environ['TRAC_ENV_PARENT_DIR'], 
                                     '.egg-cache')
        pkg_resources.set_extraction_path(egg_cache)
    from trac.web import cgi_frontend
    cgi_frontend.run()
except SystemExit:
    raise
except Exception, e:
    import sys
    import traceback

    print>>sys.stderr, e
    traceback.print_exc(file=sys.stderr)

    print 'Status: 500 Internal Server Error'
    print 'Content-Type: text/plain'
    print
    print 'Oops...'
    print
    print 'Trac detected an internal error:', e
    print
    traceback.print_exc(file=sys.stdout)
