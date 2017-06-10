Using Docker in production (experimental)
---------------------------

To install `docker-compose`, see the official Docker docs https://docs.docker.com/compose/install/.

Download the repo or clone it and enter it:
```
git clone https://github.com/zulip/zulip.git
```

Use `docker-compose up` to start Zulip in the container.
Stop the containers using `docker-compose stop` or `Ctrl+C`. Modify the config files to your needs.
The config files are located in your data volume/directory, by default it is `/opt/docker/zulip/zulip`.
After setting all required config options, start Zulip again with `docker-compose up`.

**Please note: If you change the database configuration, change it in the Zulip
configuration too and in the `docker-compose.yml`.**

If you have modified the config aka `docker-compose.yml` file correctly, you
should now have a working Zulip running on port 80/http, 443/https.

Configuration
=============

Every configuration option can be added as a environment variable.
The environment variable has to begin with `SETTING_setting_name`.

Please refer to the official Zulip documentation on how to configure Zulip.

Creating or Adding your Certificates
====================================

If you already have Certificates, rename your key to `zulip.key` and your
certificate to `zulip.combined-chain.crt` and put them into your certs folder
in the data volume path on the host system.

You can generate your self-signed SSL certificates
by using the following guide [our SSL certificate documentation](ssl-certificates.html),
but you don't have to as a certificate is generated automatically by the image on start up if none is given.

Congratulations! You have now added your SSL certificate to be used in the Docker image.

Running in the background
=========================

Add the `-d` argument to your `docker-compose up`, like this `docker-compose -d up`.

Persistent Data Volume
======================

The default data volume location of the Zulip container on the host system is `/opt/docker/zulip/zulip`.
The default data volume location of the PostgreSQL server on the host system is `/opt/docker/zulip/postgresql`.
The default data volume location of the Redis server on the host system is `/opt/docker/zulip/redis`.
To change it modify the path(s) in the `docker-compose.yml`.

**NOTE** To keep your data safe. Don't delete the data on the host system.
A deletion of the data on the host system is a direct deletion of the data.

Backups
=======
The Docker image has an in-built automatic backup mechanism.
By default a backup will be created every day at 3:30am (`30 3 * * *`).
The backups are stored in `/data/backups` directory. For example on your host
(when using the default volume paths), the path to the backups would be `/opt/docker/zulip/zulip/backups`.

To manually trigger a backup. Exec into the Zulip container and run `entrypoint.sh app:backup`.
This will automatically create a backup in your backups directory.
