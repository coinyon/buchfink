#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import setup


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


install_requires_replacements = {}

install_requirements = list(set(
    install_requires_replacements.get(requirement.strip(), requirement.strip())
    for requirement in open('requirements.txt')
    if not requirement.lstrip().startswith('#')
))

version = '0.0.6'

setup(
    name='buchfink',
    author='Aleister Coinley',
    author_email='coinyon@uberhax0r.de',
    description=('Plain Crypto Taxes'),
    license='BSD-3',
    keywords='accounting tax-report portfolio asset-management cryptocurrencies commandline',
    url='https://github.com/coinyon/buchfink',
    packages=['buchfink'],
    package_data={
        "buchfink": ["data/*.yaml"],
    },
    install_requires=install_requirements,
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    long_description=read('README.md'),
    classifiers=[
        'Development Status :: 1 - Planning',
        'Topic :: Utilities',
    ],
    entry_points={
        'console_scripts': [
            'buchfink = buchfink.cli:buchfink',
        ],
    },
)
