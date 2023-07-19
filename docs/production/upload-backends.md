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
to upload files to Amazon S3 (or an S3-compatible block storage
provider supported by the `boto` library).

## S3 backend configuration

Here, we document the process for configuring Zulip's S3 file upload
backend. To enable this backend, you need to do the following:

1. In the AWS management console, create a new IAM account (aka API
   user) for your Zulip server, and two buckets in S3, one for uploaded
   files included in messages, and another for user avatars. You need
   two buckets because the "user avatars" bucket is generally configured
   as world-readable, whereas the "uploaded files" one is not.

1. Set `s3_key` and `s3_secret_key` in /etc/zulip/zulip-secrets.conf
   to be the S3 access and secret keys for the IAM account.
   Alternately, if your Zulip server runs on an EC2 instance, set the
   IAM role for the EC2 instance to the role.

1. Set the `S3_AUTH_UPLOADS_BUCKET` and `S3_AVATAR_BUCKET` settings in
   `/etc/zulip/settings.py` to be the names of the S3 buckets you
   created (e.g. `"exampleinc-zulip-uploads"`).

1. Comment out the `LOCAL_UPLOADS_DIR` setting in
   `/etc/zulip/settings.py` (add a `#` at the start of the line).

1. If you are using a non-AWS block storage provider,
   you need to set the `S3_ENDPOINT_URL` setting to your
   endpoint url (e.g. `"https://s3.eu-central-1.amazonaws.com"`).

   For certain AWS regions, you may need to set the `S3_REGION`
   setting to your default AWS region's code (e.g. `"eu-central-1"`).

1. Finally, restart the Zulip server so that your settings changes
   take effect
   (`/home/zulip/deployments/current/scripts/restart-server`).

It's simplest to just do this configuration when setting up your Zulip
server for production usage. Note that if you had any existing
uploading files, this process does not upload them to Amazon S3; see
[migration instructions](#migrating-from-local-uploads-to-amazon-s3-backend)
below for those steps.

## S3 local caching

For performance reasons, Zulip stores a cache of recently served user
uploads on disk locally, even though the durable storage is kept in
S3. There are a number of parameters which control the size and usage
of this cache, which is maintained by nginx:

- `s3_memory_cache_size` controls the in-memory size of the cache
  _index_; the default is 1MB, which is enough to store about 8 thousand
  entries.
- `s3_disk_cache_size` controls the on-disk size of the cache
  _contents_; the default is 200MB.
- `s3_cache_inactive_time` controls the longest amount of time an
  entry will be cached since last use; the default is 30 days. Since
  the contents of the cache are immutable, this serves only as a
  potential additional limit on the size of the contents on disk;
  `s3_disk_cache_size` is expected to be the primary control for cache
  sizing.

These defaults are likely sufficient for small-to-medium deployments.
Large deployments, or deployments with image-heavy use cases, will
want to increase `s3_disk_cache_size`, potentially to be several
gigabytes. `s3_memory_cache_size` should potentially be increased,
based on estimating the number of files that the larger disk cache
will hold.

You may also wish to increase the cache sizes if the S3 storage (or
S3-compatible equivalent) is not closely located to your Zulip server,
as cache misses will be more expensive.

## nginx DNS nameserver configuration

The S3 cache described above is maintained by nginx. nginx's configuration
requires an explicitly-set DNS nameserver to resolve the hostname of the S3
servers; Zulip defaults this value to the first nameserver found in
`/etc/resolv.conf`, but this resolver can be [adjusted in
`/etc/zulip/zulip.conf`][s3-resolver] if needed. If you adjust this value, you
will need to run `/home/zulip/deployments/current/scripts/zulip-puppet-apply` to
update the nginx configuration for the new value.

[s3-resolver]: deployment.md#nameserver

## S3 bucket policy

The best way to do the S3 integration with Amazon is to create a new IAM user
just for your Zulip server with limited permissions. For both the user uploads
bucket and the user avatars bucket, you'll need to adjust the [S3 bucket
policy](https://awspolicygen.s3.amazonaws.com/policygen.html).

The file uploads bucket should have a policy of:

```json
{
    "Version": "2012-10-17",
    "Id": "Policy1468991802320",
    "Statement": [
        {
            "Sid": "Stmt1468991795370",
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
            "Sid": "Stmt1468991795371",
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

The file-uploads bucket should not be world-readable. See the
[documentation on the Zulip security model](security-model.md) for
details on the security model for uploaded files.

However, the avatars bucket is intended to be world-readable, so its
policy should be:

```json
{
    "Version": "2012-10-17",
    "Id": "Policy1468991802321",
    "Statement": [
        {
            "Sid": "Stmt1468991795380",
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
            "Sid": "Stmt1468991795381",
            "Effect": "Allow",
            "Principal": {
                "AWS": "ARN_PRINCIPAL_HERE"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::BUCKET_NAME_HERE"
        },
        {
            "Sid": "Stmt1468991795382",
            "Effect": "Allow",
            "Principal": {
                "AWS": "*"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::BUCKET_NAME_HERE/*"
        }
    ]
}
```

## Migrating from local uploads to Amazon S3 backend

As you scale your server, you might want to migrate the uploads from
your local backend to Amazon S3. Follow these instructions, step by
step, to do the migration.

1. First, [set up the S3 backend](#s3-backend-configuration) in the settings
   (all the auth stuff), but leave `LOCAL_UPLOADS_DIR` set -- the
   migration tool will need that value to know where to find your uploads.
2. Run `./manage.py transfer_uploads_to_s3`. This will upload all the
   files from the local uploads directory to Amazon S3. By default,
   this command runs on 6 parallel processes, since uploading is a
   latency-sensitive operation. You can control this parameter using
   the `--processes` option.
3. Once the transfer script completes, disable `LOCAL_UPLOADS_DIR`, and
   restart your server (continuing the last few steps of the S3
   backend setup instructions).

Congratulations! Your uploaded files are now migrated to S3.

**Caveat**: The current version of this tool does not migrate an
uploaded organization avatar or logo.

## S3 data storage class

In general, uploaded files in Zulip are accessed frequently at first, and then
age out of frequent access. The S3 backend provides the [S3
Intelligent-Tiering][s3-it] [storage class][s3-storage-class] which provides
cheaper storage for less frequently accessed objects, and may provide overall
cost savings for large deployments.

You can configure Zulip to store uploaded files using Intelligent-Tiering by
setting `S3_UPLOADS_STORAGE_CLASS` to `INTELLIGENT_TIERING` in `settings.py`.
This setting can take any of the following [storage class
value][s3-storage-class-constant] values:

- `STANDARD`
- `STANDARD_IA`
- `ONEZONE_IA`
- `REDUCED_REDUNDANCY`
- `GLACIER_IR`
- `INTELLIGENT_TIERING`

Setting `S3_UPLOADS_STORAGE_CLASS` does not affect the storage class of existing
objects. In order to change those, for example to `INTELLIGENT_TIERING`, perform
an in-place copy:

    aws s3 cp --storage-class INTELLIGENT_TIERING --recursive \
        s3://your-bucket-name/ s3://your-bucket-name/

Note that changing the lifecycle of existing objects will incur a [one-time
lifecycle transition cost][s3-pricing].

[s3-it]: https://aws.amazon.com/s3/storage-classes/intelligent-tiering/
[s3-storage-class]: https://aws.amazon.com/s3/storage-classes/
[s3-storage-class-constant]: https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html#AmazonS3-PutObject-request-header-StorageClass
[s3-pricing]: https://aws.amazon.com/s3/pricing/
