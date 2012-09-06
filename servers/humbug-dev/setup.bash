#!/bin/bash -xe

# Run the script from the directory where it lives, so we can
# easily access config files etc.
cd "$(dirname "$(readlink -f $0)")"

if ! [ -f apache/certs/humbug-self-signed.key ]; then
    echo "Copy humbug-self-signed.key to $(pwd)/apache/certs, but don't check it into git"
    exit 1
fi

# Configure sshd to disallow password logins
cat >>/etc/ssh/sshd_config <<EOF

# added by setup.bash
PasswordAuthentication no
EOF
service ssh restart

# Create users and secure homedirs
adduser --disabled-login wiki
chmod 700 /home/{humbug,wiki}

# Resize the filesystem to fill the EBS volume
resize2fs /dev/xvda1

# Add squeeze-backports and install packages
cat >>/etc/apt/sources.list <<EOF
deb http://backports.debian.org/debian-backports squeeze-backports main
deb-src http://backports.debian.org/debian-backports squeeze-backports main
EOF
apt-get update
apt-get upgrade
apt-get install sudo emacs vim screen git python-tz sqlite3 apache2 gitit python-tornado \
    python-pip
apt-get install -t squeeze-backports python-django

# Configure Apache
a2enmod proxy proxy_http rewrite auth_digest ssl
rm -f /etc/apache2/sites-enabled/*
cp apache/sites/* /etc/apache2/sites-available/
ln -s ../sites-available/humbug-default /etc/apache2/sites-enabled/000-default
ln -s ../sites-available/wiki           /etc/apache2/sites-enabled/001-wiki
ln -s ../sites-available/app            /etc/apache2/sites-enabled/002-app

# Create the Apache wiki user database
mkdir -p /etc/apache2/users
touch /etc/apache2/users/wiki
chown www-data:www-data /etc/apache2/users/wiki
chmod 600 /etc/apache2/users/wiki

# Copy in the self-signed SSL certificate
mkdir -p /etc/apache2/certs
cp apache/certs/humbug-self-signed.{crt,key} /etc/apache2/certs/
chown root:root /etc/apache2/certs/*
chmod 644 /etc/apache2/certs/*.crt
chmod 600 /etc/apache2/certs/*.key

# Restart Apache
service apache2 restart

# Configure the wiki
mkdir -p /home/wiki/wiki/static/img
cp wiki/gitit.conf /home/wiki/wiki/
cp wiki/logo.png   /home/wiki/wiki/static/img/
cp wiki/custom.css /home/wiki/wiki/static/css/
chown -R wiki:wiki /home/wiki/wiki

# Install Python packages from PyPi
# FIXME: make this more secure
pip install django-jstemplate
