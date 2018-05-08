#!/usr/bin/env python

"""
Slider web application.

:copyright: (c) 2015 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

from __future__ import (
    division, absolute_import, print_function, unicode_literals)

import collections
import os
import os.path

from typing import Any, Dict, List, Tuple

import flask
from flask import (g, request, Response, render_template, url_for)

from slider import commands

APP = flask.Flask(__name__)
RENDERER = {
    '.md': 'pandoc',
    '.txt': 'asciidoc',
}


FileInfo = collections.namedtuple(
    'FileInfo', 'name view_url render_name slide_url note_url')


def get_full_filename(filename: str) -> Any:
    """Return full file name."""
    config = APP.config_slider["DEFAULT"]  # pylint: disable=no-member
    return os.path.join(config['root_dir'], filename)


def get_file_info(fname: str, filename: str) -> FileInfo:
    """Return information about given file."""
    _, ext = os.path.splitext(fname)
    view_url = url_for("view_path", pathname=filename)
    try:
        render_name = RENDERER[ext]
        slide_url = url_for(
            "view_path", pathname=filename, render=render_name + "_slide")
        note_url = url_for(
            "view_path", pathname=filename, render=render_name + "_note")
    except KeyError:
        return FileInfo(fname, view_url, None, None, None)

    return FileInfo(fname, view_url, render_name, slide_url, note_url)


def get_dir_info(dirname: str) -> Tuple[List[Tuple[str, str]], List[FileInfo]]:
    """Return information about included directories and files."""
    fulldirname = get_full_filename(dirname)
    dirs = []
    files = []
    for fname in os.listdir(fulldirname):
        if fname[0] == '.':
            continue
        fullname = os.path.join(fulldirname, fname)
        pathname = os.path.join(dirname, fname)
        if os.path.isdir(fullname):
            dirs.append((fname, url_for("view_path", pathname=pathname)))
        elif os.path.isfile(fullname):
            files.append(get_file_info(fname, pathname))
    dirs.sort()
    files.sort()
    return dirs, files


def get_pandoc_style_url(style: str) -> Any:
    """Return URL of assets for given slide style."""
    style_url = url_for('static', filename=style)
    if style == 's5':
        style_url += '/ui/default'
    return style_url


@APP.route("/")
def index() -> Any:
    """Render root directory."""
    dirs, files = get_dir_info("")
    return render_template("index.html", name="ROOT", dirs=dirs, files=files)


def render_pandoc_slide(
        real_filename: str,
        config: Dict[str, str],
        slide_style: str) -> Response:
    """Render slide with pandoc."""
    return Response(commands.pandoc_slides(
        real_filename, config, slide_style, get_pandoc_style_url(slide_style)))


def render_pandoc_note(
        real_filename: str, config: Dict[str, str], slide_style: str) -> Any:
    # pylint: disable=unused-argument
    """Render PDF via Pandoc."""
    pdf_name = commands.pandoc_notes(real_filename, config)
    pdfs = getattr(g, 'pdfs_to_delete', [])
    g.pdfs_to_delete = pdfs + [pdf_name]
    as_attachment = bool(request.args.get("attachment", False))
    attachment_name = os.path.splitext(
        os.path.basename(real_filename))[0] + '.pdf'
    return flask.send_file(
        pdf_name,
        as_attachment=as_attachment,
        attachment_filename=attachment_name)


def render_asciidoc_slide(
        real_filename: str,
        config: Dict[str, str],
        slide_style: str) -> Response:
    # pylint: disable=unused-argument
    """Render slides via Asciidoc."""
    return Response(commands.asciidoc_slides(real_filename, config))


def render_asciidoc_note(
        real_filename: str,
        config: Dict[str, str],
        slide_style: str) -> Response:
    # pylint: disable=unused-argument
    """Render notes via Asciidoc."""
    return Response(commands.asciidoc_notes(real_filename, config))


def send_file_or_404(filename: str) -> Any:
    """Send the file to the browser or send a 404."""
    try:
        return flask.send_file(filename)
    except FileNotFoundError:
        flask.abort(404)
        return ""


@APP.route("/<path:pathname>")
def view_path(pathname: str) -> Any:
    """Render the given path."""
    config = APP.config_slider["DEFAULT"]  # pylint: disable=no-member
    temp_dir = config["tempdir"]
    temp_link = config["templink"]
    if pathname.startswith(temp_link[1:]):
        return send_file_or_404(temp_dir + pathname[len(temp_link)-2:])
    real_pathname = flask.safe_join(config['root_dir'], pathname)
    if os.path.isdir(real_pathname):
        dirs, files = get_dir_info(pathname)
        return render_template(
            "index.html", name=pathname, dirs=dirs, files=files)
    real_filename = os.path.abspath(real_pathname)

    render = request.args.get("render")
    if render:
        render_func = globals().get("render_" + render)
        if render_func:
            slide_style = request.args.get("style", config['slide_style'])
            return render_func(real_filename, config, slide_style)
    return send_file_or_404(real_filename)


@APP.teardown_appcontext
def remove_pdf(
        exception: Exception) -> None:  # pylint: disable=unused-argument
    """Remove all generated PDF files."""
    pdfs = getattr(g, 'pdfs_to_delete', [])
    for pdf in pdfs:
        os.unlink(pdf)
    g.pdfs_to_delete = []
