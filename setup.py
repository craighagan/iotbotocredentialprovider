#!/usr/bin/env python

import os
from setuptools import setup, find_packages

setup(name='iotbotocredentialprovider',
      version='1.0',
      description='AWS IoT Credential Provider: create boto sessions which obtain and renew credentials from an AWS IoT device certificate',
      author='Craig I. Hagan',
      author_email='hagan@cih.com',
      url='n/a',
      packages = find_packages(exclude=["test"]),
      install_requires=["boto3","requests"],
      setup_requires=["pytest-runner"],
      tests_require=["pytest", "pytest-runner"],
)
