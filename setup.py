#!/usr/bin/env python

from setuptools import setup

with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='pxctl',
    version='0.1.0',
    description='Picaso Designer X PRO ctl',
    long_description=readme,
    url='',
    license=license,
    install_requires=['tabulate'],
    zip_safe=False,
    packages=['pxctl'],
    entry_points={
        "console_scripts": [
            "pxctl = pxctl.pxctl:main"
        ]
    }
)

