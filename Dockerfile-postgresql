# To build run `docker build -f Dockerfile-postgresql .` from the root of the
# zulip repo.

# Install build tools and build tsearch_extras for the current postgres
# version. Currently the postgres images do not support automatic upgrading of
# the on-disk data in volumes. So the base image can not currently be upgraded
# without users needing a manual pgdump and restore.
FROM postgres:10
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
        postgresql-server-dev-$PG_MAJOR \
        postgresql-server-dev-all \
        git \
        build-essential \
        fakeroot \
        devscripts
RUN git clone https://github.com/zulip/tsearch_extras.git \
    && cd tsearch_extras \
    && echo $PG_MAJOR > debian/pgversions \
    && pg_buildext updatecontrol \
    && debuild -b -uc -us

# Install tsearch_extras, hunspell, zulip stop words, and run zulip database
# init.
FROM postgres:10
ENV TSEARCH_EXTRAS_VERSION=0.4
ENV TSEARCH_EXTRAS_DEB=postgresql-${PG_MAJOR}-tsearch-extras_${TSEARCH_EXTRAS_VERSION}_amd64.deb
COPY --from=0 /${TSEARCH_EXTRAS_DEB} /tmp
COPY puppet/zulip/files/postgresql/zulip_english.stop /usr/share/postgresql/$PG_MAJOR/tsearch_data/zulip_english.stop
COPY scripts/setup/postgres-create-db /docker-entrypoint-initdb.d/postgres-create-db.sh
COPY scripts/setup/pgroonga-debian.asc /tmp
RUN apt-key add /tmp/pgroonga-debian.asc \
    && echo "deb http://packages.groonga.org/debian/ stretch main" > /etc/apt/sources.list.d/zulip.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
       hunspell-en-us \
       postgresql-${PG_MAJOR}-pgroonga \
    && DEBIAN_FRONTEND=noninteractive dpkg -i /tmp/${TSEARCH_EXTRAS_DEB} \
    && rm /tmp/${TSEARCH_EXTRAS_DEB} \
    && ln -sf /var/cache/postgresql/dicts/en_us.dict "/usr/share/postgresql/$PG_MAJOR/tsearch_data/en_us.dict" \
    && ln -sf /var/cache/postgresql/dicts/en_us.affix "/usr/share/postgresql/$PG_MAJOR/tsearch_data/en_us.affix" \
    && rm -rf /var/lib/apt/lists/*
