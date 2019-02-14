# File upload backends

Zulip in production supports a couple different backends for storing
files uploaded by users of the Zulip server (messages, profile
pictures, organization icons, custom emoji, etc.).

The default is the `LOCAL_UPLOADS_DIR` backend, which just stores
files on disk in the specified directory on the Zulip server.
Obviously, this backend doesn't work with multiple Zulip servers and
doesn't scale, but it's great for getting a Zulip server up and
running quickly. You can later migrate the uploads to S3 by
[following the instructions here](#migrating-from-local-uploads-to-amazon-s3-backend).

We also support an `S3` backend, which uses the Python `boto` library
to upload files to Amazon S3 (and, with some work, it should be
possible to use any other storage provider compatible with `boto`).

## S3 backend configuration

Here, we document the process for configuring Zulip's S3 file upload
backend.  To enable this backend, you need to do the following:

1. In the AWS management console, create a new IAM account (aka API
user) for your Zulip server, and two buckets in S3, one for uploaded
files included in messages, and another for user avatars.  You need
two buckets because the "user avatars" bucket is generally configured
as world-readable, whereas the "uploaded files" one is not.

1. Set `s3_key` and `s3_secret_key` in /etc/zulip/zulip-secrets.conf
to be the S3 access and secret keys for the IAM account.

1. Set the `S3_AUTH_UPLOADS_BUCKET` and `S3_AVATAR_BUCKET` settings in
`/etc/zulip/settings.py` to be the names of the S3 buckets you
created (e.g. `exampleinc-zulip-uploads`).

1. Comment out the `LOCAL_UPLOADS_DIR` setting in
`/etc/zulip/settings.py` (add a `#` at the start of the line).

1. In some AWS regions, you need to explicitly
    [configure boto](http://boto.cloudhackers.com/en/latest/boto_config_tut.html)
    to use AWS's SIGv4 signature format (because AWS has stopped
    supporting the older v3 format in those regions).  You can do this
    by adding an `/etc/zulip/boto.cfg` containing the following:
    ```
    [s3]
    use-sigv4 = True
    # Edit to provide your S3 bucket's AWS region here.
    host = s3.eu-central-1.amazonaws.com
    ```


1. You will need to configure `nginx` to direct requests for uploaded
    files to the Zulip server (which will then serve a redirect to the
    appropriate place in S3), rather than serving them directly.

    With Zulip 1.9.0 and newer, you can do this automatically with the
    following commands run as root:

    ```
    crudini --set /etc/zulip/zulip.conf application_server no_serve_uploads true
    /home/zulip/deployments/current/scripts/zulip-puppet-apply
    ```

    (The first line will update your `/etc/zulip/zulip.conf`).

    With older Zulip, you need to edit
    `/etc/nginx/sites-available/zulip-enterprise` to comment out the
    `nginx` configuration block for `/user_avatars` and the `include
    /etc/nginx/zulip-include/uploads.route` line and then reload the
    `nginx` service (`service nginx reload`).

1. Finally, restart the Zulip server so that your settings changes
   take effect
   (`/home/zulip/deployments/current/scripts/restart-server`).

It's simplest to just do this configuration when setting up your Zulip
server for production usage.  Note that if you had any existing
uploading files, this process does not upload them to Amazon S3.  If
you have an existing server and are upgrading to the S3 backend, ask
in [#production help on chat.zulip.org][production-help] for advice on
how to migrate your data.

[production-help]: https://chat.zulip.org/#narrow/stream/31-production-help

## S3 bucket policy

The best way to do the S3 integration with Amazon is to create a new
IAM user just for your Zulip server with limited permissions.  For
each of the two buckets, you'll want to
[add an S3 bucket policy](https://awspolicygen.s3.amazonaws.com/policygen.html)
entry that looks something like this:

```
{
    "Version": "2012-10-17",
    "Id": "Policy1468991802321",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "AWS": "ARN_PRINCIPAL_HERE"
            },
            "Action": [
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::BUCKET_NAME_HERE/*"
        },
        {
            "Sid": "Stmt1468991795389",
            "Effect": "Allow",
            "Principal": {
                "AWS": "ARN_PRINCIPAL_HERE"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::BUCKET_NAME_HERE"
        }
    ]
}
```

The avatars bucket is intended to be world-readable, so you'll also
need a block like this:

```
{
    "Sid": "Stmt1468991795389",
    "Effect": "Allow",
    "Principal": {
        "AWS": "*"
    },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::BUCKET_NAME_HERE/*"
}

```

The file-uploads bucket should not be world-readable.  See the
[documentation on the Zulip security model](security-model.html) for
details on the security model for uploaded files.

## Migrating from local uploads to Amazon S3 backend

As you scale your server, you might want to migrate the uploads from
your local backend to Amazon S3.  Follow these instructions, step by
step, to do the migration.

1. First, [setup the S3 backend](#s3-backend-configuration) in the settings
    (all the auth stuff), but leave `LOCAL_UPLOADS_DIR` set -- the
    migration tool will need that value to know where to find your uploads.
2. Run `./manage.py transfer_uploads_to_s3`. This will upload all the
    files from the local uploads directory to Amazon S3. By default,
    this command runs on 6 parallel processes, since uploading is a
    latency-sensitive operation.  You can control this parameter using
    the `--processes` option.
3. Once the transer script compltes, disable `LOCAL_UPLOADS_DIR`, and
    restart your server (continuing the last few steps of the S3
    backend setup instructions).

Congratulations!  Your uploaded files are now migrated to S3.

**Caveat**: The current version of this tool does not migrate an
  uploaded organization avatar or logo.
