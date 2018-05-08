#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for slide-filter.

:copyright: (c) 2016 by Detlef Stern
:license: Apache 2.0, see LICENSE
"""

from slider import slide_filter


def test_quotes():
    filter = slide_filter.GermanQuotesFilter()
    assert filter.replace_quotes("´´Hallo", None) == "Hallo"
    assert filter.replace_quotes("Welt´´", None) == "Welt"
