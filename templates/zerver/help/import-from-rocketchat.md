# Import from Rocketchat

To be able to convert the data, a (local) development environment is required,
since the `bson` module from `mongodump` is only available in the development
environment.

### Set up development environment

```
mkdir ~/dev/
cd ~/dev
git clone https://github.com/zulip/zulip.git
git checkout -b <tag_name> <tag_name>
vagrant up --provider=docker
```

Since the directory with the repo is not shared between docker container and
host, a directory created under it, will be reachable from outside and inside
the container.

```
# in ~/dev/zulip
mkdir tmp
```

### Export rocketchat data

Dump the data into the `tmp` dir `~/dev/zulip/tmp`

```
/usr/bin/mongodump \
 --host=127.0.0.1 \
 --port=27017 \
 --db=parties \
 --out=~/dev/zulip/tmp/mongodump
```

### Convert the data

Switch to the development environment with

```
vagrant ssh
```

and execute the conversion command

```
rm -fR tmp/export
./manage.py convert_rocketchat_data \
 --output ./tmp/export \
 --rocketchat_dump ./tmp/mongodump/parties/
```
Leave the development environment and find the data in `~/dev/zulip/tmp/export`
and `~/dev/zulip/tmp/export.tar.gz`

### Import data

Copy the `export.tar.gz` over to the target host, unpack it and then execute
the import command.

```bash
# As zulip runuser
tar -xzf foo.tar.gz -C /tmp/
/usr/bin/supervisorctl stop all
sudo -u zulip ./manage.py import "" /tmp/srv/zulip/tmp/export
/usr/bin/supervisorctl start all
```

