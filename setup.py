from setuptools import setup

setup(
    name='TCPOverICMP',
    version='1.0.0',
    author='Heli Zilberman',
    author_email='helyzilberman@gmail.com',
    url='https://github.com/HeliZilberman/TCPOverICMP',
    license='',
    description='A Tunnel Implementation for TCP over ICMP',
    packages=['TCPOverICMP'],
    install_requires=[
        'protobuf',
    ],
    entry_points={
        'console_scripts': [
            'proxy_client = TCPOverICMP.proxy_client_main:run_async_loop',
            'proxy_server = TCPOverICMP.proxy_server_main:run_async_loop',
        ],
    },
)