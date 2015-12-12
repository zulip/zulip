## How to configure the container

See the [Configuration](https://github.com/Galexrt/docker-zulip/wiki/Configuration) Page for infos about configuring the container to suit your needs.

***

## How to get the container:
### For docker use:
`docker pull quay.io/galexrt/zulip:v1.3.9`

***

## **Configure your `docker-compose.yml`, before running the container!**
**If you don't configure it, you'll end up with a misconfigured Zulip Instance!**

***

## Starting the container
To start the container, you have to use either use `docker-compose` or `kubernetes`:

**Don't forget to configure the `docker-compose.yml`!**
### Using docker-compose:
Change your current path to the source folder and run `docker-compose up` to start zulip.
