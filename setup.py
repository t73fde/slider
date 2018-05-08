#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import setup, find_packages

if __name__ == "__main__":
    here = os.path.abspath(".")
    README = open(os.path.join(here, 'README.rst')).read()
    # CHANGES = open(os.path.join(here, 'CHANGELOG')).read()

    setup(
        name="slider",
        description="serves slides and handouts",
        long_description=README,
        version='0.0.1',
        packages=find_packages(),
        include_package_data=True,
        zip_safe=False,
        install_requires=[
            'Flask',
            'pandocfilters',
            'typing',
        ],
        license="APL2",
        url="https://github.com/t73fde/slider",
        maintainer="Detlef Stern",
        maintainer_email="mail-slider@yoyod.de",
        keywords="edu slide web",
        classifiers=[
            "Development Status :: 1 - Planning",
            "Environment :: Web Environment",
            "Framework :: Flask",
            "Intended Audience :: Education",
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3",
        ],
        entry_points={
            'console_scripts': [
                'slider = slider.main:main',
                'slide_preprocessor = slider.slide_preprocessor:main',
            ],
        }
    )
