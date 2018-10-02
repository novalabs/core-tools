from setuptools import setup

setup(
    name='novalabs',
    version='0.1',
    packages=['novalabs'],
    install_requires = ['pySerial>=3.4',
                            'GitPython',
                            'tabulate',
                            'argcomplete',
                            'colorama',
                            'jsonschema',
                            'intelhex'
                            ],
    url='https://github.com/novalabs/core-tools',
    license='GPLv3',
    author='Davide Rizzi',
    author_email='d.rizzi@novalabs.io',
    description='Nova Core Python tools'
)