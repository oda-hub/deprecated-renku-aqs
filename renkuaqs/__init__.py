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
import logging
import pyvis
import shutil
import os
import json

import renkuaqs.graph_utils as graph_utils

from . import config
from functools import partial
from pip._vendor import pkg_resources
from renku.version import __version__
from http.server import SimpleHTTPRequestHandler
from git import Repo


logging.basicConfig(level="DEBUG")


def _check_renku_version():
    """Check renku version."""

    _package = pkg_resources.working_set.by_key["renku"]
    required_version = _package.parsed_version.public

    if required_version != __version__:
        logging.info(f"You are using renku version {__version__}, however version {required_version} "
                     f"is required for the renku-aqs plugin.\n"
                     "You should consider install the suggested version.",)


class HTTPGraphHandler(SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, *args, **kwargs) -> None:
        super().__init__(request, client_address, *args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)


    def do_GET(self) -> None:
        mount_path_env = os.environ.get('MOUNT_PATH', None)
        logging.info(f'self.path = {self.path}, os.cwd = {os.getcwd()}, mount_path = {mount_path_env}')
        if self.path == '/':

            try:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                graph_utils.inspect_oda_graph_inputs(None, paths=os.getcwd())
                graph_html_content, ttl_content = graph_utils.build_graph_html(None, paths=os.getcwd(),
                                                                               template_location="remote",
                                                                               include_ttl_content_within_html=False)
                self.wfile.write(graph_html_content.encode())
            except Exception as e:
                output_html = f'''
                <html><head></head><body><h1>Error while generating the output graph:</h1>
                <p>{e}</p>
                </body>
                </html>
                '''
                self.wfile.write(output_html.encode())
                logging.warning(f"Error while generating the output graph: {e}")

        if self.path == '/graph_version':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            repo = Repo('.')
            sha = repo.head.commit.hexsha
            short_sha = repo.git.rev_parse(sha, short=8)
            logging.info(f"Graph version, git revision is: {short_sha}")
            self.wfile.write(short_sha.encode())

        if self.path.startswith('/ttl_graph'):
            graph_ttl_content = graph_utils.extract_graph(None, paths=os.getcwd())
            logging.info(f"ttl graph = {graph_ttl_content[0:100]}")
            repo = Repo('.')
            sha = repo.head.commit.hexsha
            short_sha = repo.git.rev_parse(sha, short=8)
            logging.info(f"Graph version, git revision is: {short_sha}")

            output_obj = {
                'graph_ttl_content': graph_ttl_content,
                'graph_version': short_sha
            }
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(json.dumps(output_obj).encode())

        if self.path == '/lib/bindings/utils.js':
            pyvis_package_path = pyvis.__path__[0]
            shutil.copy(pyvis_package_path)
            logging.info(f'lib bindings utils js path {self.path}')
            logging.info(f'Graph http server GET pointing at : {self.path}')
            super().do_GET()



def _start_graph_http_server(*args):
    logging.info(args)

    ap = argparse.ArgumentParser()
    ap.add_argument('wwwroot')
    ap.add_argument('port')
    args = ap.parse_args(args)

    logging.info(args)

    from http.server import HTTPServer
    server = HTTPServer(
        ('localhost', int(args.port)),
        partial(HTTPGraphHandler, directory=args.wwwroot),
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
            f'python -c \'import renkuaqs; import os; from renku.domain_model.project_context import project_context; '
                f'project_context.push_path(os.getcwd()); renkuaqs._start_graph_http_server("{mount_dir}", "{{port}}")\''
        ],
        'new_browser_tab': False,
        'launcher_entry': {
                'enabled': True,
                'icon_path': os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "graph_icon.svg"),
                'title': 'Graph'
            }
        }


_check_renku_version()
