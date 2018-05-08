#!/usr/bin/env python

"""
Calling external programs in an orderes manner.

:copyright: (c) 2015 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

from __future__ import (
    division, absolute_import, print_function, unicode_literals)

import os
import os.path
import subprocess
import tempfile

from typing import Any, Dict, List

import flask

__all__ = (
    'pandoc_slides', 'pandoc_notes', 'asciidoc_slides', 'asciidoc_notes',
)

APP = flask.Flask(__name__)
APP_PATH = os.path.dirname(APP.static_folder)


def get_slider_env(config: Dict[str, str]) -> Dict[str, str]:
    """Return a clean environment for calling commands."""
    useful_keys = {
        "HOME", "LANG", "PATH", }
    env = {
        key: value
        for (key, value) in os.environ.items()
        if key in useful_keys
    }
    env['SLIDER_PID'] = str(os.getpid())
    env['SLIDER_TEMPDIR'] = config["tempdir"]
    env['SLIDER_TEMPLINK'] = config["templink"]
    return env


def execute_pipe(
        config: Dict[str, str], command_list: List[List[str]]) -> List[bytes]:
    """Execute a pip of commands and return standard output of the last."""
    env = get_slider_env(config)
    previous_process = None
    stdin_code = None
    for command in command_list:
        print("EXEC", " ".join(command))
        if command[0] == '*cd':
            os.chdir(command[1])
            continue
        process = subprocess.Popen(
            command,
            bufsize=0,
            stdin=stdin_code,
            stdout=subprocess.PIPE,
            env=env,
            universal_newlines=False)
        if previous_process:
            previous_process.stdout.close()
        previous_process = process
        stdin_code = previous_process.stdout
    return list(process.stdout)


def get_script_path(scriptname: Any) -> Any:
    """Return full path of local script."""
    return os.path.join(APP_PATH, scriptname)


def get_preprocessor_command(
        rootname: str,
        basename: str,
        includes: List[str],
        filename: str,
        slides: bool) -> List[str]:
    """Calculate preprocessor command, based on file name and slide switch."""
    command = [
        'slide_preprocessor',
        '-R', rootname,
        '-B', basename,
        '-P', 'html']
    for path in includes:
        command.extend(["-I", path])
    if slides:
        command.extend(['-D', 'slides'])
    command.append(filename)
    return command


def get_include_paths(config: Dict[str, str]) -> List[str]:
    """Calculate the list of directories where files should be searched for."""
    colon_sep_values = config['include_paths']
    path_list = [value.strip() for value in colon_sep_values.split(':')]
    if path_list:
        return path_list
    return [os.path.join(config['root_dir'], "pandoc")]


def pandoc_slides(
        filename: str,
        config: Dict[str, str],
        slide_style: str,
        style_url: str) -> List[bytes]:
    """Create Pandoc slide view."""
    bib_path = config['bibpath']
    cite_style = config['cite_style']
    pandoc_command = [
        'pandoc', '-f', 'markdown+smart', '-s',
        '-F', 'pandoc-citeproc',
        '--csl', cite_style,
        '--bibliography', bib_path,
        '-F', get_script_path("slide_filter.py"),
        '--slide-level', '2', '-t', slide_style
    ]
    if slide_style in ('s5', 'slidy', 'slideous', 'revealjs'):
        pandoc_command.extend(['-V', slide_style + '-url=' + style_url])
    return execute_pipe(config, [
        get_preprocessor_command(
            rootname=config['root_dir'],
            basename=config['root_dir'],
            includes=get_include_paths(config),
            filename=filename,
            slides=True),
        pandoc_command
    ])


def pandoc_notes(filename: str, config: Dict[str, str]) -> str:
    """Create Pandoc note file via LaTeX as as PDF."""
    bib_path = config['bibpath']
    cite_style = config['cite_style']
    out_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    out_file.close()
    pandoc_command = [
        'pandoc', '-f', 'markdown+smart',
        '--pdf-engine=xelatex',
        '-F', 'pandoc-citeproc',
        '--csl', cite_style,
        '--bibliography', bib_path,
        '-F', get_script_path("slide_filter.py"),
        '-o', out_file.name,
        '-V', 'documentclass=scrartcl',
        '-V', 'margin-left=1in',
        '-V', 'margin-top=1in',
    ]

    execute_pipe(config, [
        get_preprocessor_command(
            rootname=config['root_dir'],
            basename=os.path.dirname(filename),
            includes=get_include_paths(config),
            filename=filename,
            slides=False),
        ['*cd', os.path.dirname(filename)],
        pandoc_command,
        ['*cd', config['root_dir']],
    ])
    return out_file.name


def asciidoc_slides(filename: str, config: Dict[str, str]) -> List[bytes]:
    """Create Asciidoc slide view."""
    return execute_pipe(
        config, [['asciidoc', '-a', 'beamer', '-o', '-', filename]])


def asciidoc_notes(filename: str, config: Dict[str, str]) -> List[bytes]:
    """Create Asciidoc note view."""
    return execute_pipe(
        config, [['asciidoc', '-a', 'script', '-o', '-', filename]])
