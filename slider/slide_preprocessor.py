#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Slide preprocessor.

Since Pandoc does not allow to include other files nor does not provide some
form of selective processing, I need a preprocessor that does it for me.

Moreover, it allows to searhc for the included files.

Two styles of specifying the preprocessor command are possible:

    * html: <!--command opt-arg-->
    * hash: #command opt-arg

:copyright: (c) 2015 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

from __future__ import (
    division, absolute_import, print_function, unicode_literals)

import argparse
import os
import os.path
import pathlib
import re
import sys

from typing import (
    cast,
    Callable, Iterator, List, NamedTuple, Optional, Sequence, Set, TextIO)
from typing import Dict, Tuple  # NOQA, pylint: disable=unused-import

SYMBOL_SLIDES = 'slides'

COMMAND_RE = '[a-z#]+'
ARGUMENT_RE = '\\S+'


def gen_parse_line(
        regexp_str: str) -> Callable[[str], Optional[Sequence[str]]]:
    """Return a function parsing input lines for commands."""
    regexp = re.compile(regexp_str.format(COMMAND_RE, ARGUMENT_RE))

    def result(line: str) -> Optional[Sequence[str]]:
        """Syntax specific line parser."""
        match_obj = regexp.match(line)
        if not match_obj:
            return None
        return match_obj.groups()

    return result


LINE_PARSER = {
    'hash': gen_parse_line(r'^\s*#({})(?:\s+({}))?$'),
    'html': gen_parse_line(r'^\s*<!--\s*({})(?:\s+({}))?\s*-->\s*$'),
}


class FileInfo(object):
    """Wrap a file object to gain more data about reading it."""

    def __init__(self, prev: Optional['FileInfo'], fileobj: TextIO) -> None:
        """Intitialize with a file object."""
        self.prev = prev
        self._fileobj = fileobj
        self.name = fileobj.name
        self.directory = None if self.name == "<stdin>" \
            else os.path.dirname(self.name)
        self.line = 0
        self._eof = False

    def readline(self) -> str:
        """Return the next line.

        IMPORTANT: if an end-of-file is detected, an empty line is returned.
        This is because of some markdown problems if several include commands
        are in subsequent lines. This situation can be detected by a double
        line number.
        """
        if self._eof:
            return ''
        line = self._fileobj.readline()
        if not line:
            self._eof = True
            return "\n"
        self.line += 1
        return line

    def close(self) -> Optional['FileInfo']:
        """Close the file object."""
        self._fileobj.close()
        return self.prev

    def is_already_open(self, filename: str) -> bool:
        """Determine whether the given file is already opened."""
        current = self  # type: Optional[FileInfo]
        while current is not None:
            if current.name == filename:
                return True
            current = current.prev
        return False

    def __str__(self) -> str:
        """Return printable information about file object."""
        return "{}, line {}".format(self._fileobj, self.line)

    def __repr__(self) -> str:
        """Return representation of file object."""
        return "<{}>".format(str(self))


Config = NamedTuple('Config', [
    ('root', str),
    ('base', str),
    ('includes', List[str]),
    ('symbols', Set[str])])


class SlidePreprocessor(object):
    """Read all given input files and pre-process them."""

    def __init__(
            self,
            config: Config,
            files: List[TextIO],
            parse_line: Callable) -> None:
        """Initialize a slide preprocessor."""
        self._config = config
        self._files = list(files)
        self._current = None  # type: Optional[FileInfo]
        self._next_file()
        self._parse_line = parse_line
        self._do_emit = True
        self._if_stack = []  # type: List[bool]

        if config.base:
            parts = pathlib.PurePath(config.base).parts
            self._reldir = os.path.join(
                '', *['..' for i in range(len(parts) - 1)])
        else:
            self._reldir = ''

    def _next_file(self) -> None:
        self._current = FileInfo(None, self._files[0])
        self._files = self._files[1:]

    def _emit(self, line: str) -> None:
        if self._do_emit:
            # print(self._current.name, self._current.line, line)
            print(line)

    def _has_symbol(self, symbol: str) -> bool:
        return symbol.lower() in self._config.symbols

    def _handle_comment(  # pylint: disable=no-self-use
            self, _ignored: str) -> None:  # pylint: disable=unused-argument
        """Ignore the whole line."""

    def _handle_page(self) -> None:
        self._emit('')
        if self._has_symbol(SYMBOL_SLIDES):
            self._emit('----')
            self._emit('')

    def _handle_pause(self) -> None:
        if self._has_symbol(SYMBOL_SLIDES):
            self._emit('')
            self._emit('. . .')
            self._emit('')

    def _handle_ifdef(self, symbol: str) -> None:
        self._if_stack.append(self._do_emit)
        self._do_emit = self._has_symbol(symbol)

    def _handle_ifndef(self, symbol: str) -> None:
        self._if_stack.append(self._do_emit)
        self._do_emit = not self._has_symbol(symbol)

    def _handle_elifdef(self, symbol: str) -> None:
        if self._if_stack:
            self._do_emit = self._has_symbol(symbol)

    def _handle_else(self) -> None:
        if self._if_stack:
            self._do_emit = not self._do_emit

    def _handle_endif(self) -> None:
        if self._if_stack:
            self._do_emit = self._if_stack[-1]
            del self._if_stack[-1]

    def _candidate_names(self, filepath: str) -> Iterator[str]:
        """Iterate through al search directories, yielding candidate names."""
        current_dir = cast(FileInfo, self._current).directory
        if current_dir is not None:
            search_list = [current_dir] + self._config.includes
        else:
            search_list = list(self._config.includes)
        for dir_name in search_list:
            candidate_name = os.path.join(dir_name, filepath)
            yield candidate_name

    def _handle_include(self, filepath: str) -> None:
        recursive = False
        for candidate_name in self._candidate_names(filepath):
            if cast(FileInfo, self._current).is_already_open(candidate_name):
                recursive = True
                continue
            try:
                new_file = open(candidate_name, "r", encoding="utf-8")
                self._current = FileInfo(self._current, new_file)
                return
            except FileNotFoundError:
                pass
        if recursive:
            self._emit("Recursive include: {}".format(filepath))
        else:
            self._emit("File not found: {}".format(filepath))

    def _handle_image(self, filepath: str) -> None:
        for candidate_name in self._candidate_names(filepath):
            if not os.path.isfile(candidate_name):
                continue
            assert candidate_name.startswith(self._config.root)
            candidate_name = candidate_name[len(self._config.root)+1:]
            # TODO this needs to be elaborated
            # Preprocessor must know sliders Filename<->URL mapping
            candidate_url = "." + candidate_name
            if self._reldir:
                candidate_url = os.path.join(self._reldir, candidate_name)
            else:
                candidate_url = "/" + candidate_name
            self._emit("![]({})\\ ".format(candidate_url))
            return
        self._emit("Image not found: {}".format(filepath))

    ARG_COMMANDS = {
        '#': (_handle_comment, False),
        'ifdef': (_handle_ifdef, True),
        'ifndef': (_handle_ifndef, True),
        'elifdef': (_handle_elifdef, True),
        'include': (_handle_include, False),
        'image': (_handle_image, False),
    }  # type: Dict[str, Tuple[Callable[[SlidePreprocessor, str], None], bool]]
    NOARG_COMMANDS = {
        'page': (_handle_page, False),
        'pause': (_handle_pause, False),
        'else': (_handle_else, True),
        'endif': (_handle_endif, True),
    }

    def _handle_command(self, command: str, argument: str) -> bool:
        """Process a detected command."""
        arg_handler_info = self.ARG_COMMANDS.get(command)
        if arg_handler_info:
            arg_handler, always = arg_handler_info
            if not self._do_emit and not always:
                return False
            arg_handler(self, argument)
            return True
        noarg_handler_info = self.NOARG_COMMANDS.get(command)
        if noarg_handler_info:
            noarg_handler, always = noarg_handler_info
            if not self._do_emit and not always:
                return False
            noarg_handler(self)
            return True
        return False

    def handle_line(self, line: str) -> None:
        """Process one line."""
        command_tuple = self._parse_line(line)
        if command_tuple:
            command, argument = command_tuple
            if not self._handle_command(command, argument):
                self._emit(line)
        else:
            self._emit(line)

    def _readline(self) -> str:
        """Read one line, switch to the next file."""
        while True:
            if self._current is None:
                if not self._files:
                    return ''
                self._next_file()
            current = cast(FileInfo, self._current)
            result = current.readline()
            if result:
                return result
            self._current = current.close()

    def run(self) -> None:
        """Read and process all input files."""
        while True:
            line = self._readline()
            if not line:
                return
            line = line.rstrip('\n\r')
            self.handle_line(line)


def directory(root: Optional[str], name: Optional[str]) -> str:
    """Handle name of directory."""
    if name is None or not os.path.isdir(name):
        name = os.getcwd()
    result = os.path.abspath(name)
    if root is not None:
        if not result.startswith(root):
            result = root
    return result


def include_directories(includes: List[str]) -> List[str]:
    """Clean all given include directory names."""
    if not includes:
        return []
    result = []
    for name in includes:
        if not os.path.isdir(name):
            continue
        result.append(os.path.abspath(name))
    return result


def main() -> None:
    """Execute the main program."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-R', '--root', metavar='root', help='root directory')
    parser.add_argument(
        '-B', '--base', metavar='root', help='base directory')
    parser.add_argument(
        '-D', '--define', metavar='sym', action='append', help='define symbol')
    parser.add_argument(
        '-s', '--slides', action='store_true',
        help='define symbol "{}"'.format(SYMBOL_SLIDES))
    parser.add_argument(
        '-I', '--include', metavar='dir', action='append',
        help='add directory to include search path')
    parser.add_argument(
        '-P', '--parser', default='hash', choices=('hash', 'html'),
        help='select line parser')
    parser.add_argument(
        'file', nargs='*',
        type=argparse.FileType('r', encoding='utf-8'),
        help='file to read')
    args = parser.parse_args()

    root = directory(None, args.root)
    symbols = set(symbol.lower() for symbol in args.define or [])
    if args.slides:
        symbols.add(SYMBOL_SLIDES)
    config = Config(
        root=root,
        base=directory(root, args.base)[len(root):],
        includes=include_directories(args.include),
        symbols=symbols)
    files = list(args.file) if args.file else [sys.stdin]
    app = SlidePreprocessor(config, files, LINE_PARSER[args.parser])
    try:
        app.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
