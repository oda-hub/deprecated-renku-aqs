# -*- coding: utf-8 -*-
#
# Copyright 2020 - 
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, print_function

import argparse
import sys
import logging
import pyvis
import shutil
import os

from . import config
from functools import partial
import renkuaqs.plugin as aqsPlugin

logging.basicConfig(level="DEBUG")

from http.server import SimpleHTTPRequestHandler

class GetGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, *args, **kwargs) -> None:
        super().__init__(request, client_address, *args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def do_GET(self) -> None:
        if self.path == '/':
            aqsPlugin.build_graph(paths=os.getcwd(), template_location="remote")
            if os.path.exists(os.path.join(os.getcwd(), 'graph.html')):
                if 'MOUNT_PATH' in os.environ:
                    self.path = os.path.join(os.environ['MOUNT_PATH'], 'graph.html')
                else:
                    self.path = 'graph.html'

        if self.path == '/lib/bindings/utils.js':
            pyvis_path = pyvis_package_path = pyvis.__path__[0]
            shutil.copy(pyvis_package_path, )
            # self.path = os.path.join(pyvis_package_path, 'lib/bindings/utils.js')
            logging.info(f'lib bindings utils js path {self.path}')

        logging.info(f'Graph http server GET pointing at : {self.path}')
        super().do_GET()


def _start_graph_http_server(**kwargs):
    logging.info(kwargs)

    ap = argparse.ArgumentParser()
    ap.add_argument('wwwroot')
    ap.add_argument('port')
    args = ap.parse_args(kwargs)

    from http.server import HTTPServer
    server = HTTPServer(
        ('localhost', int(args.port)),
        partial(GetGraphHandler, directory=args.wwwroot),
        )
    logging.info(f'Starting graph server with args {args}, use <Ctrl-C> to stop')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    server.server_close()
    logging.info("Graph server stopped.")

def setup_graph_visualizer():

    mount_dir = '/home/jovyan'
    if 'MOUNT_PATH' in os.environ:
        mount_dir = os.path.join(mount_dir, os.environ['MOUNT_PATH'][1:])

    return {
        'command': [
            'bash',
            '-c',
            f'python \'import renkuaqs; renkuaqs._start_graph_http_server(wwwroot={mount_dir}, port={{port}})\''
        ],
        'new_browser_tab': True,
        'launcher_entry': {
                'enabled': True,
                'icon_path': '/tmp/graph_icon.svg',
                'title': 'Graph'
            }
        }
