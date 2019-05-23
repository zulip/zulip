from setuptools import setup, find_packages

with open('requirements/dev.txt') as rfp:
    reqs = [i for i in rfp.read().split('\n') if not (i.startswith('#') or len(i) == 0)]
setup(
    name='zulip',
    version='2.0.0',
    url='https://github.com/zulip/zulip',
    author='zulip',
    packages=find_packages(),
    install_requires=reqs,
)
