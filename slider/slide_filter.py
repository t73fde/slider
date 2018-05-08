#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Slide filter.

Filter and substitude content to be used for my slides.

The following actions are done:

    * Substitute meta variables ("%{metavar}")

:copyright: (c) 2015 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

import hashlib
import os
import os.path
import re
import subprocess
import sys
import traceback

from typing import Any, Dict, List, Optional, Pattern, Tuple

from pandocfilters import (
    get_caption, toJSONFilters,
    CodeBlock, Image, Link, Para, Plain, Str, Strong)


PANDOC_SLIDE_FORMATS = {'s5', 'slidy', 'slideous', 'dzslides', 'revealjs'}
PANDOC_HTML_FORMATS = {'html', 'html5'} | PANDOC_SLIDE_FORMATS


class FilterBase:
    """Base class for all my filters."""

    def __call__(
            self, key: str, value: Any, output_format: str, meta: str) -> Any:
        """Process JSON elements.

        For each key, this method calls a method "process_key" (with a lower
        case key). Therefore it dispatches the action calls to appropriate
        methods. If there is no such method, nothing is changed.
        """
        # print(key, output_format, repr(value), file=sys.stderr)
        action = getattr(self, 'process_' + key.lower(), None)
        if action is None:
            # print(key, output_format, repr(value), file=sys.stderr)
            return None
        try:
            return action(value, output_format, meta)
        except Exception as exc:  # pylint: disable=broad-except
            print(traceback.format_exc(), file=sys.stderr)
            return Plain([Strong([Str("Filter error: " + str(exc))])])

    @staticmethod
    def stringify_elem(elem: Dict[str, Any]) -> Any:
        """Transform a Pandoc JSON list element value into a string."""
        elem_type = elem['t']
        if elem_type == 'Str':
            return elem['c']
        if elem_type == 'Space':
            return ' '
        return str(elem)

    @staticmethod
    def stringify_elem_list(elem_list: List[Dict[str, Any]]) -> List[Any]:
        """Transform a Pandoc list into a string."""
        return [FilterBase.stringify_elem(elem) for elem in elem_list]


class FileBasedFilter(FilterBase):
    """A filter that writes content to temporary files."""

    def __init__(self, temp_dir: str, temp_link: str) -> None:
        """Create a file-based filter.

        A file-based filter wirtes contents to temporary files. The names of
        theses files are based on some content.
        """
        self.temp_dir = temp_dir
        self.temp_link = temp_link

    def get_filename4code(
            self,
            filter_name: str,
            content: str,
            extension: str) -> Tuple[str, str]:
        """Generate filename based on content.

        Returns both the full file name as well as the relative file name.
        The latter is relative to the temp-dir.
        """
        filter_dir = os.path.join(self.temp_dir, filter_name)
        try:
            os.makedirs(filter_dir)
            print("Created directory", filter_dir, file=sys.stderr)
        except FileExistsError:
            pass
        digested_name = hashlib.sha256(
            content.encode(sys.getfilesystemencoding())).hexdigest()
        filename = digested_name + "." + extension
        fullname = os.path.join(filter_dir, filename)
        relpath = filter_name + "/" + filename
        return (fullname, relpath)


class GraphvizFilter(FileBasedFilter):
    """Translates a fenced code block via graphviz to a SVG/PNG image."""

    def generate_file(
            self,
            graphviz_class: str,
            code: str,
            image_format: str) -> Tuple[str, str]:
        """Generate an image file from graphviz code.

        Returns both full file name and relative file name.
        """
        fullname, relpath = self.get_filename4code(
            graphviz_class, code, image_format)
        if not os.path.isfile(fullname):
            print(
                "Call '{}' to create {}".format(graphviz_class, fullname),
                file=sys.stderr)
            process = subprocess.Popen(
                [graphviz_class, "-T", image_format, "-o", fullname],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE)
            (_output, _errors) = process.communicate(code.encode("utf8"))
        return fullname, relpath

    def process_codeblock(
            self,
            value: Tuple[Tuple[str, List[str], Dict[str, str]], str],
            output_format: str, meta: Dict[str, str]) -> Any:
        # pylint: disable=unused-argument
        """Fenced blocks are code blocks."""
        [[ident, classes, keyvals], code] = value
        for graphviz_class in ["dot", "neato", "twopi", "circo", "fdp"]:
            if graphviz_class in classes:
                caption, typef, keyvals = get_caption(keyvals)
                if output_format in PANDOC_HTML_FORMATS:
                    _, relpath = self.generate_file(
                        graphviz_class, code, "svg")
                    image_ref = self.temp_link + relpath
                else:
                    image_ref, _ = self.generate_file(
                        graphviz_class, code, "png")
                return Para(
                    [Image([ident, [], keyvals], caption, [image_ref, typef])])
        if "graphviz" in classes:
            new_classes = [
                "dot" if cls == "graphviz" else cls for cls in classes]
            return CodeBlock([ident, new_classes, keyvals], code)
        return None


class BlockdiagFilter(FileBasedFilter):
    """Translates a fenced code block via blockdiag to a SVG/PNG image."""

    FILTER_CLASSES = {
        "blockdiag", "seqdiag", "actdiag", "nwdiag", "packetdiag", "rackdiag",
    }

    def generate_file(
            self,
            diag_class: str,
            code: str,
            image_format: str) -> Tuple[str, str]:
        """Generate an image file from graphviz code.

        Returns both full file name and relative file name.
        """
        extension = image_format
        fullname, relpath = self.get_filename4code(diag_class, code, extension)
        if not os.path.isfile(fullname):
            diag_fullname, _ = self.get_filename4code(
                diag_class, code, diag_class)
            with open(diag_fullname, "w") as diag_file:
                print(code, file=diag_file)
            print(
                "Call '{}' to create {}".format(diag_class, fullname),
                file=sys.stderr)
            process = subprocess.Popen(
                [diag_class, "-T", image_format, "-o", fullname,
                 diag_fullname],
                stderr=subprocess.PIPE)
            (_output, errors) = process.communicate()
            if errors:
                print(errors.decode("utf-8"), file=sys.stderr)
        return fullname, relpath

    def process_codeblock(
            self,
            value: Tuple[Tuple[str, List[str], Dict[str, str]], str],
            output_format: str, meta: Dict[str, str]) -> Any:
        # pylint: disable=unused-argument
        """Fenced blocks are code blocks."""
        [[ident, classes, keyvals], code] = value
        for diag_class in self.FILTER_CLASSES:
            if diag_class in classes:
                caption, typef, keyvals = get_caption(keyvals)
                if output_format in PANDOC_HTML_FORMATS:
                    _, relpath = self.generate_file(
                        diag_class, code, "svg")
                    image_ref = self.temp_link + relpath
                else:
                    image_ref, _ = self.generate_file(
                        diag_class, code, "png")
                return Para(
                    [Image([ident, [], keyvals], caption, [image_ref, typef])])
        return None


class SvgFilter(FileBasedFilter):
    """Transforms SVG imaages to PNG images for LaTeX/PDF output."""

    @staticmethod
    def substitute_png4svg(root_ref: str) -> Optional[str]:
        """Try to find a corresponding PNG image and return its name."""
        png_image_ref = root_ref + ".png"
        return png_image_ref if os.path.isfile(png_image_ref) else None

    def convert_svg_to_png(self, image_ref: str) -> Optional[str]:
        """Convert SVG to PNG file and return file name of PNG file."""
        try:
            with open(image_ref) as svg_file:
                code = svg_file.read()
        except FileNotFoundError:
            return None

        fullname, _ = self.get_filename4code("convert", code, "png")
        if not os.path.isfile(fullname):
            print("Call 'convert' to create", fullname, file=sys.stderr)
            process = subprocess.Popen(
                ["convert", image_ref, fullname],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            process.wait()
        return fullname

    def process_image(
            self,
            value: Tuple[Any, str, Tuple[str, Any]],
            output_format: str, meta: Dict[str, str]) -> Any:
        # pylint: disable=unused-argument
        """Transform SVG to PNG via existing file."""
        if output_format != "latex":
            return None
        [image_meta, caption, [image_ref, typef]] = value
        root_ref, extension = os.path.splitext(image_ref)
        if extension.lower() != ".svg":
            return None
        new_image_ref = self.substitute_png4svg(root_ref) or \
            self.convert_svg_to_png(image_ref)
        if new_image_ref:
            return Image(image_meta, caption, [new_image_ref, typef])
        return None


class GermanQuotesFilter(FilterBase):
    """Translates "´´" to left and right german quotes."""

    def __init__(self) -> None:
        """Initialize the filter."""
        self.is_opening_quote = True

    def _quote_replacement(self, output_format: str) -> str:
        if output_format in PANDOC_HTML_FORMATS:
            return "\u201e" if self.is_opening_quote else "\u201c"
            # return "&bdquo;" if self.is_opening_quote else "&lsquo;"
        if output_format == "latex":
            return "\u201e" if self.is_opening_quote else "\u201c"
        if not output_format:
            return ''
        print(output_format, file=sys.stderr)
        return ""

    def replace_quotes(self, value: str, output_format: str) -> Optional[str]:
        """Replace all (german) quote chars with equivalent unicode chars.

        The string ´´ toggles opening and closing quote.
        """
        current_value = value
        result = ''
        changed = False
        while True:
            pos = current_value.find("´´")
            if pos < 0:
                if changed:
                    return result + current_value
                return None
            changed = True
            if pos > 0:
                result += current_value[0:pos]
            result += self._quote_replacement(output_format)
            current_value = current_value[pos+2:]
            self.is_opening_quote = not self.is_opening_quote

    def process_str(
            self, value: str, output_format: str, meta: Dict[str, str]) -> Any:
        # pylint: disable=unused-argument
        """Process all string elements."""
        val = self.replace_quotes(value, output_format)
        if val is not None:
            return Str(val)
        return None


class MetaVarFilter(FilterBase):
    """Injects meta variable into text."""

    def __init__(self) -> None:
        """Initialize the filter."""
        self._metavar_pattern_text = re.compile("%\\{(.*?)\\}")
        self._metavar_pattern_link = re.compile("%%7B(.*?)%7D")

    @staticmethod
    def _find_variables(
            value: str, pattern: Pattern) -> List[Tuple[str, int, int]]:
        result = []
        pos = 0
        while pos < len(value):
            match_obj = pattern.search(value, pos)
            if match_obj is None:
                break
            pos = match_obj.end()
            result.append((match_obj.group(1), match_obj.start(), pos))
        return result

    @staticmethod
    def _lookup_variable(
            variable: str, meta: Dict[str, Dict[str, Any]]) -> Any:
        meta_value = meta.get(variable, {})
        meta_type = meta_value.get('t')
        if meta_type == 'MetaInlines':
            return ''.join(FilterBase.stringify_elem_list(meta_value['c']))
        if meta_type == 'MetaString':
            return meta_value['c']
        return None

    def replace_metavar(
            self,
            string_value: str,
            meta: Dict[str, Dict[str, Any]],
            pattern: Pattern) -> Optional[str]:
        """Replace all occurences of metavar in string with its value."""
        variable_infos = self._find_variables(string_value, pattern)
        if variable_infos:
            value_infos = [
                (self._lookup_variable(var, meta), start, end)
                for var, start, end in variable_infos]
            result = list(string_value)
            for var, start, end in reversed(value_infos):
                if var is not None:
                    result[start:end] = var
            return ''.join(result)
        return None

    def process_link(
            self,
            value: Tuple[str, List[Dict[str, str]], List[str]],
            output_format: str,
            meta: Dict[str, Dict[str, Any]]) -> Any:
        # pylint: disable=unused-argument
        """Process a link element."""
        link_info, link_texts, link_values = value
        changed = False
        new_texts = []
        for text_obj in link_texts:
            if text_obj.get('t') == 'Str':
                val = self.replace_metavar(
                    text_obj['c'], meta, self._metavar_pattern_text)
                if val is not None:
                    new_texts.append({'t': 'Str', 'c': val})
                    changed = True
                    continue
            new_texts.append(text_obj)
        new_values = []
        for link_string in link_values:
            val = self.replace_metavar(
                link_string, meta, self._metavar_pattern_link)
            if val is not None:
                changed = True
                new_values.append(val)
            else:
                new_values.append(link_string)
        if changed:
            return Link(link_info, new_texts, new_values)
        return None

    def process_str(
            self,
            value: str,
            output_format: str,
            meta: Dict[str, Dict[str, Any]]) -> Any:
        # pylint: disable=unused-argument
        """Process all string elements."""
        val = self.replace_metavar(value, meta, self._metavar_pattern_text)
        return Str(val) if val is not None else None


if __name__ == '__main__':
    TEMP_DIR = os.environ["SLIDER_TEMPDIR"]
    TEMP_LINK = os.environ["SLIDER_TEMPLINK"]
    toJSONFilters([
        MetaVarFilter(),
        GermanQuotesFilter(),
        GraphvizFilter(TEMP_DIR, TEMP_LINK),
        BlockdiagFilter(TEMP_DIR, TEMP_LINK),
        SvgFilter(TEMP_DIR, TEMP_LINK),
    ])
