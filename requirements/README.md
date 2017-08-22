The dependency graph of the requirements is as follows:

```
dev         prod
+ +          +
| +->common<-+
v
mypy,docs,py3k
```

Of the files, only dev, prod, py3k, and mypy have been used in the install
scripts directly. The rest are implicit dependencies.

common and dev are locked.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to 6.0.0 in
common.txt and propagate it to dev_lock.txt and prod_lock.txt:
0. Replace `ipython==5.4.1` with `ipython==6.0.0` in common.txt
1. Run './tools/update-locked-requirements'
2. Run `./tools/provision` to install the new deps and test them
3. Commit your changes.

The reason the steps to remove the `-e` is necessary is because `pip-compile`
doesn't support installing from vcs without `-e` yet.
You may track the ongoing progress here https://github.com/jazzband/pip-tools/issues/355.
