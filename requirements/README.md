The dependency graph of the requirements is as follows:

```
dev         prod
+ +          +
| +->common<-+
v
mypy,docs
```

Of the files, only dev, prod, and mypy have been used in the install
scripts directly. The rest are implicit dependencies.

common and dev are locked.

Steps to update a lock file, e.g. to update ipython from 5.3.0 to 6.0.0 in
common.txt and propagate it to dev_lock.txt and prod_lock.txt:
0. Replace `ipython==5.4.1` with `ipython==6.0.0` in common.txt
1. Run './tools/update-locked-requirements'
2. Increase `PROVISION_VERSION` in `version.py`.
3. Run `./tools/provision` to install the new deps and test them
4. Commit your changes.
