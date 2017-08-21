The dependency graph of the requirements is as follows:

```
py3_dev          py3_prod
+  + +              +
|  | +->py3_common<-+
|  |    |   +
| dev   |   v
|  |    |py3_socialauth
|  |    |
|  |    |
|  |    |
|  v    +---------->emailmirror
|  docs,py3k
|
v
mypy
```

Of the files, only py3_dev, py3_prod, and mypy have been used in the install
scripts directly. The rest are implicit dependencies.

py3_common and dev locked.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to 6.0.0 in
common.txt and propagate it to py3_common_lock:
0. Replace `ipython==5.4.1` with `ipython==6.0.0` in common.txt
1. Run './tools/update-locked-requirements'

The reason the steps to remove the `-e` is necessary is because `pip-compile`
doesn't support installing from vcs without `-e` yet.
You may track the ongoing progress here https://github.com/jazzband/pip-tools/issues/355.
