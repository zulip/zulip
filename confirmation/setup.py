from setuptools import setup, find_packages

# Dynamically calculate the version based on confirmation.VERSION.                                                          
version_tuple = __import__('confirmation').VERSION
if version_tuple[2] is not None:
    version = "%d.%d_%s" % version_tuple
else:
    version = "%d.%d" % version_tuple[:2]


setup(
    name = 'django-confirmation',
    version = version,
    description = 'Generic object confirmation for Django',
    author = 'Jarek Zgoda',
    author_email = 'jarek.zgoda@gmail.com',
    url = 'http://code.google.com/p/django-confirmation/',
    license = 'New BSD License',
    packages = find_packages(),
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Utilities',
    ],
    zip_safe = False,
    install_requires = [
        'django>=1.0',
    ],
)

