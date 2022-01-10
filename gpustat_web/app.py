"""
gpustat.web


MIT License

Copyright (c) 2018-2020 Jongwook Choi (@wookayin)
"""

from typing import List, Tuple, Optional
import os
import sys
import traceback
import urllib
import ssl

import asyncio
import asyncssh
import aiohttp

from datetime import datetime
from collections import OrderedDict, Counter

from termcolor import cprint, colored
from aiohttp import web
import aiohttp_jinja2 as aiojinja2


__PATH__ = os.path.abspath(os.path.dirname(__file__))

DEFAULT_GPUSTAT_COMMAND = "gpustat --color --gpuname-width 25"


###############################################################################
# Background workers to collect information from nodes
###############################################################################

class Context(object):
    '''The global context object.'''
    def __init__(self):
        self.host_status = OrderedDict()
        self.interval = 5.0

    def host_set_message(self, hostname: str, msg: str):
        self.host_status[hostname] = colored(f"({hostname}) ", 'white') + msg + '\n'


context = Context()

###############################################################################
# webserver handlers.
###############################################################################

# monkey-patch ansi2html scheme. TODO: better color codes
import ansi2html
scheme = 'solarized'
ansi2html.style.SCHEME[scheme] = list(ansi2html.style.SCHEME[scheme])
ansi2html.style.SCHEME[scheme][0] = '#555555'
ansi_conv = ansi2html.Ansi2HTMLConverter(dark_bg=True, scheme=scheme)


def render_gpustat_body():
    body = ''
    for host, status in context.host_status.items():
        if not status:
            continue
        body += status
    return ansi_conv.convert(body, full=False)


async def handler(request):
    '''Renders the html page.'''

    data = dict(
        ansi2html_headers=ansi_conv.produce_headers().replace('\n', ' '),
        http_host=WS_URL,
        interval=int(context.interval * 1000)
    )
    response = aiojinja2.render_template('index.html', request, data)
    response.headers['Content-Language'] = 'en'
    return response


###############################################################################
# app factory and entrypoint.
###############################################################################

def create_app(*,
               ssl_certfile: Optional[str] = None,
               ssl_keyfile: Optional[str] = None,
               exec_cmd: Optional[str] = None):
    if not exec_cmd:
        exec_cmd = DEFAULT_GPUSTAT_COMMAND

    app = web.Application()
    app.router.add_get('/', handler)

    # jinja2 setup
    import jinja2
    aiojinja2.setup(app,
                    loader=jinja2.FileSystemLoader(
                        os.path.join(__PATH__, 'template'))
                    )

    # SSL setup
    if ssl_certfile and ssl_keyfile:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=ssl_certfile,
                                    keyfile=ssl_keyfile)

        cprint(f"Using Secure HTTPS (SSL/TLS) server ...", color='green')
    else:
        ssl_context = None   # type: ignore
    return app, ssl_context


WS_URL = ""
def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ws", type=str, help="The URL of the WebSocket to use.")
    parser.add_argument('--port', type=int, default=48109,
                        help="Port number the web application will listen to. (Default: 48109)")
    parser.add_argument('--interval', type=float, default=5.0,
                        help="Interval (in seconds) between two consecutive requests.")
    parser.add_argument('--ssl-certfile', type=str, default=None,
                        help="Path to the SSL certificate file (Optional, if want to run HTTPS server)")
    parser.add_argument('--ssl-keyfile', type=str, default=None,
                        help="Path to the SSL private key file (Optional, if want to run HTTPS server)")
    parser.add_argument('--exec', type=str,
                        default=DEFAULT_GPUSTAT_COMMAND,
                        help="command-line to execute (e.g. gpustat --color --gpuname-width 25)")
    args = parser.parse_args()

    global WS_URL
    WS_URL = args.ws

    cprint(f"Cmd   : {args.exec}", color='yellow')

    if args.interval > 0.1:
        context.interval = args.interval

    app, ssl_context = create_app(
        ssl_certfile=args.ssl_certfile, ssl_keyfile=args.ssl_keyfile,
        exec_cmd=args.exec)

    web.run_app(app, host='0.0.0.0', port=args.port,
                ssl_context=ssl_context)

if __name__ == '__main__':
    main()
