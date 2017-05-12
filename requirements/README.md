The dependency graph of the requirements is as follows:

```
py3_dev          py3_prod py2_prod
+  + +              +  +  +   +
|  | +->py3_common<-+  v  v   +>py2_common+----+
|  |    |   +          prod     |    +         |
|  |    |   v                   |    v         |
|  |    |py3_socialauth         |py2_socialauth|
|  v    |                       |              |
| >dev  +--->common<------------+              |
| | +           +                              |
| | v           +-->emailmirror                |
| |docs,moto,py3k,twisted                      |
| +-----------------------------------+py2_dev<+
v
mypy
```

Of the files, only py2_dev, py2_prod, py3_dev, py3_prod, and mypy have been
used in the install scripts directly. The rest are implicit dependencies.

py2_common and py3_common are locked.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to 6.0.0 in
common.txt and propagate it py2_common_lock.txt and py3_common_lock:
0. Replace `ipython==5.4.1` with `ipython==6.0.0` in common.txt
1. Run './tools/update-locked-requirements'

The reason the steps to remove the `-e` is necessary is because `pip-compile`
doesn't support installing from vcs without `-e` yet.
You may track the ongoing progress here https://github.com/jazzband/pip-tools/issues/355.
