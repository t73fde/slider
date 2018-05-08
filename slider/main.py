#!/usr/bin/env python

"""
Main module slider.

:copyright: (c) 2015 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

from __future__ import (
    division, absolute_import, print_function, unicode_literals)

import argparse
import configparser
import mimetypes
import os
import os.path
import sys
import tempfile

from slider.webapp import APP


class ConfigParser(
        configparser.ConfigParser,
        configparser.BasicInterpolation):
    # pylint: disable=too-many-ancestors
    """Specialized config parser."""

    def __init__(self) -> None:
        """Initialize the config parser."""
        super().__init__()
        module_name = sys.modules[__name__].__file__
        module_dir_name = os.path.dirname(module_name)
        self['DEFAULT'] = {
            'home_dir': os.path.expanduser("~"),
            'app_dir': module_dir_name,
            'root_dir': os.getcwd(),
            'include_paths': "%(root_dir)s/pandoc",
            'cite_style': "%(app_dir)s/csl/dkr-1505-2.csl",
            'slide_style': "slidy",
            'bibpath': "%(home_dir)s/texmf/bibtex/bib/stern.bib",
            'tempdir': os.path.join(tempfile.gettempdir(), "slider"),
            'templink': "/slider-temp/",
        }


def get_config() -> ConfigParser:
    """Return application configuration."""
    config = ConfigParser()

    userdir = os.path.expanduser("~")
    config.read([
        ".slider",
        os.path.join(userdir, ".slider"),
        os.path.join(userdir, ".config", "slider"),
        "/etc/slider",
    ])
    return config


def main() -> None:
    """Execute the main program."""
    default_host = "127.0.0.1"
    default_port = 0x736c

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-B', '--no-browser', dest="browser",
        action="store_false", default=True, help="do not open browser")
    parser.add_argument(
        '-D', '--no-debug', dest="debug", action="store_false", default=True,
        help="disable debugging mode")
    parser.add_argument(
        "-H", "--host", default=default_host,
        help="Hostname of the Flask app [default %s]" % default_host)
    parser.add_argument(
        '-p', '--port', type=int, default=default_port,
        help="port number of web server [default %d]" % default_port)
    args = parser.parse_args()

    if args.browser:
        if not args.debug or os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            # Otherwise, in reload mode this code would be executed twice...
            # See werkzeug.serving.run_with_reloader()
            import threading

            def open_browser(url: str) -> None:
                """Open web browser."""
                import webbrowser
                webbrowser.open(url)

            url = "http://localhost:%d" % args.port
            timer = threading.Timer(1.0, open_browser, [url])
            timer.start()

    for ext in (
            '.dot', '.mako', '.md', '.py', '.rst', '.sh', '.snippets', '.tex',
            '.uml', '.wiki'):
        mimetypes.add_type('text/plain', ext)
    APP.config['SECRET_KEY'] = 'not very secret'
    APP.config_slider = get_config()
    if args.debug and os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        APP.config_slider.write(sys.stderr)
    APP.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
