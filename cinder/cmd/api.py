#!/usr/bin/env python
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Starter script for Cinder OS API."""

import logging as python_logging
import sys

import eventlet  # noqa
eventlet.monkey_patch()
# Monkey patch the original current_thread to use the up-to-date _active
# global variable. See https://bugs.launchpad.net/bugs/1863021 and
# https://github.com/eventlet/eventlet/issues/592
import __original_module_threading as orig_threading  # pylint: disable=E0401
import threading # noqa
orig_threading.current_thread.__globals__['_active'] = threading._active

from oslo_config import cfg
from oslo_log import log as logging
from oslo_reports import guru_meditation_report as gmr
from oslo_reports import opts as gmr_opts

from cinder import i18n  # noqa
i18n.enable_lazy()
# Need to register global_opts
from cinder.common import config
from cinder import coordination
from cinder import objects
from cinder import rpc
from cinder import service
from cinder import utils
from cinder import version

CONF = cfg.CONF


def main():
    objects.register_all()
    gmr_opts.set_defaults(CONF)
    CONF(sys.argv[1:], project='cinder',
         version=version.version_string())
    config.set_middleware_defaults()
    logging.setup(CONF, "cinder")
    python_logging.captureWarnings(True)
    utils.monkey_patch()

    gmr.TextGuruMeditation.setup_autorun(version, conf=CONF)

    coordination.COORDINATOR.start()

    rpc.init(CONF)
    launcher = service.process_launcher()
    server = service.WSGIService('osapi_volume')
    launcher.launch_service(server, workers=server.workers)
    launcher.wait()
