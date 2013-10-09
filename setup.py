#!/usr/bin/env python

from setuptools import setup


setup(
    name='cloudprefs',
    version='0.1',
    description='Cloud Preferences API',
    long_description='Cloud Preferences API for use with OpenStack',
    author='Trey Tabner',
    author_email='trey@tabner.com',
    url='https://github.com/treytabner/python-cloudprefs',
    py_modules=['cloudprefs'],
    license='Apache',
    platforms='any',
    install_requires=[
        'tornado',
        'motor',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
