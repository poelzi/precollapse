#!/usr/bin/env python

from distutils.core import setup

setup(
    name='precollapse',
    version='0.1',
    description='Information collector and sharing tool',
    long_description="""
    Precollapse allows you to create collections to bundle
    informations into topics. Each collection consists of different
    entries that are downloaded from sources like http, ftp or bittorrent.
    Collections can be exported and shared with other people.
    """,
    author='Daniel Poelzleithner',
    author_email='precollapse@poelzi.org',
    url='https://github.com/poelzi/precollapse',
    packages=['precollapse'],
    classifiers=[
        'Development Status :: 5 - Alpha',
        'Environment :: Console',
        #'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Communications',
        ],
    setup_requires=[
        "SQLAlchemy",
        "ipython", # for debugging
    ]
)
