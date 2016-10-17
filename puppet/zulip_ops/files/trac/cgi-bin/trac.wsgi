#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C)2008-2009 Edgewall Software
# Copyright (C) 2008 Noah Kantrowitz <noah@coderanger.net>
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
# Author: Noah Kantrowitz <noah@coderanger.net>
import os

def application(environ, start_request):
    if not 'trac.env_parent_dir' in environ:
        environ.setdefault('trac.env_path', '/home/zulip/trac')
    if 'PYTHON_EGG_CACHE' in environ:                                           
        os.environ['PYTHON_EGG_CACHE'] = environ['PYTHON_EGG_CACHE']
    elif 'trac.env_path' in environ:
        os.environ['PYTHON_EGG_CACHE'] = \
            os.path.join(environ['trac.env_path'], '.egg-cache')
    elif 'trac.env_parent_dir' in environ:
        os.environ['PYTHON_EGG_CACHE'] = \
            os.path.join(environ['trac.env_parent_dir'], '.egg-cache')
    from trac.web.main import dispatch_request
    return dispatch_request(environ, start_request)
