#### Unmet dependencies error

When running `vagrant up` or `provision`, if you see the following error:

```console
==> default: E:unmet dependencies. Try 'apt-get -f install' with no packages (or specify a solution).
```

It means that your local apt repository has been corrupted, which can
usually be resolved by executing the command:

```console
$ apt-get -f install
```
