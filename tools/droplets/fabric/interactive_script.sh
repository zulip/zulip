#!/usr/bin/env bash
clear

cat <<EOM

Zulip will ask you for the following two input for completing the installation:

- The email address of the person or team who should get support and error emails from this Zulip server.
- The user-accessible domain name for this Zulip server, i.e., what users will type in their web browser.

To skip the Zulip setup for now, press Ctrl+C.  You will be prompted again on your next login.

You can also re-run this setup script at any time with the command:
   bash $(readlink -f "${0}")

Please press enter when you are ready to configure Zulip.

EOM

read -r _

while  [ -z "${email}" ] && [ -z "${hostname}" ]; do
read -r -p "Enter the email address for recieving support and error emails (ex. user@example.com) " email
read -r -p "Enter the domain or subdomain pointed to this Zulip instance (ex. chat.example.com): " hostname
echo ""

done

cat <<EOM

Zulip instance is now being configured... This might take a few minutes.


EOM

sudo service nginx stop

array=(./zulip-server-*)
"${array[0]}"/scripts/setup/install --certbot --email="$email" --hostname="$hostname"

cp -f /etc/skel/.zulip_bashrc /root/.bashrc

touch /opt/zulip/.configured
