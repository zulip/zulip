# Add a custom certificate

By default, Zulip generates a signed certificate during the server install
process. In some cases, a server administrator may choose not to use that
feature, in which case your Zulip server may be using a self-signed
certificate. This is most common for Zulip servers not connected to the
public internet.

## Web

Most browsers will show a warning if you try to connect to a Zulip server
with a self-signed certificate.

If you are absolutely, 100% sure that the Zulip server you are connecting to
is supposed to have a self-signed certificate, click through the warnings
and follow the instructions on-screen.

If you are less than 100% sure, contact your server administrator. Accepting
a malicious self-signed certificate would give a stranger full access to
your Zulip, including your username and password.

## Desktop

For safety reasons, we require you to manually enter the certificate details
before you can connect to your Zulip server. You'll need to get a
certificate file (should end in `.crt` or `.pem`) from your server
administrator.

1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the lower left corner.

2. Select the **Organizations** tab.

3. Under **Add Custom Certificates**, enter your organization URL and add
   the custom certificate file (should end in `.crt` or `.pem`).
