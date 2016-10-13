# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import bitfield.models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
import zerver.models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
    ]

    if "postgres" not in settings.DATABASES["default"]["ENGINE"]:
        zulip_postgres_migrations = [] # type: ignore # https://github.com/JukkaL/mypy/issues/1164
    else:
        zulip_postgres_migrations = [
            # Full-text search
            migrations.RunSQL("""
CREATE TEXT SEARCH DICTIONARY english_us_hunspell
  (template = ispell, DictFile = en_us, AffFile = en_us, StopWords = zulip_english);
CREATE TEXT SEARCH CONFIGURATION zulip.english_us_search (COPY=pg_catalog.english);
ALTER TEXT SEARCH CONFIGURATION zulip.english_us_search
  ALTER MAPPING FOR asciiword, asciihword, hword_asciipart, word, hword, hword_part
  WITH english_us_hunspell, english_stem;

CREATE FUNCTION escape_html(text) RETURNS text IMMUTABLE LANGUAGE 'sql' AS $$
  SELECT replace(replace(replace(replace(replace($1, '&', '&amp;'), '<', '&lt;'),
                                 '>', '&gt;'), '"', '&quot;'), '''', '&#39;');
$$ ;

ALTER TABLE zerver_message ADD COLUMN search_tsvector tsvector;
CREATE INDEX zerver_message_search_tsvector ON zerver_message USING gin(search_tsvector);
ALTER INDEX zerver_message_search_tsvector SET (fastupdate = OFF);

CREATE TABLE fts_update_log (id SERIAL PRIMARY KEY, message_id INTEGER NOT NULL);
CREATE FUNCTION do_notify_fts_update_log() RETURNS trigger LANGUAGE plpgsql AS
  $$ BEGIN NOTIFY fts_update_log; RETURN NEW; END $$;
CREATE TRIGGER fts_update_log_notify AFTER INSERT ON fts_update_log
  FOR EACH STATEMENT EXECUTE PROCEDURE do_notify_fts_update_log();
CREATE FUNCTION append_to_fts_update_log() RETURNS trigger LANGUAGE plpgsql AS
  $$ BEGIN INSERT INTO fts_update_log (message_id) VALUES (NEW.id); RETURN NEW; END $$;
CREATE TRIGGER zerver_message_update_search_tsvector_async
  BEFORE INSERT OR UPDATE OF subject, rendered_content ON zerver_message
  FOR EACH ROW EXECUTE PROCEDURE append_to_fts_update_log();
"""),
            ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(default=django.utils.timezone.now, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('email', models.EmailField(unique=True, max_length=75, db_index=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_bot', models.BooleanField(default=False)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_mirror_dummy', models.BooleanField(default=False)),
                ('full_name', models.CharField(max_length=100)),
                ('short_name', models.CharField(max_length=100)),
                ('pointer', models.IntegerField()),
                ('last_pointer_updater', models.CharField(max_length=64)),
                ('api_key', models.CharField(max_length=32)),
                ('enable_stream_desktop_notifications', models.BooleanField(default=True)),
                ('enable_stream_sounds', models.BooleanField(default=True)),
                ('enable_desktop_notifications', models.BooleanField(default=True)),
                ('enable_sounds', models.BooleanField(default=True)),
                ('enable_offline_email_notifications', models.BooleanField(default=True)),
                ('enable_offline_push_notifications', models.BooleanField(default=True)),
                ('enable_digest_emails', models.BooleanField(default=True)),
                ('default_desktop_notifications', models.BooleanField(default=True)),
                ('last_reminder', models.DateTimeField(default=django.utils.timezone.now, null=True)),
                ('rate_limits', models.CharField(default='', max_length=100)),
                ('default_all_public_streams', models.BooleanField(default=False)),
                ('enter_sends', models.NullBooleanField(default=True)),
                ('autoscroll_forever', models.BooleanField(default=False)),
                ('twenty_four_hour_time', models.BooleanField(default=False)),
                ('avatar_source', models.CharField(default='G', max_length=1, choices=[('G', 'Hosted by Gravatar'), ('U', 'Uploaded by user'), ('S', 'System generated')])),
                ('tutorial_status', models.CharField(default='W', max_length=1, choices=[('W', 'Waiting'), ('S', 'Started'), ('F', 'Finished')])),
                ('onboarding_steps', models.TextField(default='[]')),
                ('invites_granted', models.IntegerField(default=0)),
                ('invites_used', models.IntegerField(default=0)),
                ('alert_words', models.TextField(default='[]')),
                ('muted_topics', models.TextField(default='[]')),
                ('bot_owner', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AppleDeviceToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('token', models.CharField(unique=True, max_length=255)),
                ('last_updated', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=30, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DefaultStream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Huddle',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('huddle_hash', models.CharField(unique=True, max_length=40, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('subject', models.CharField(max_length=60, db_index=True)),
                ('content', models.TextField()),
                ('rendered_content', models.TextField(null=True)),
                ('rendered_content_version', models.IntegerField(null=True)),
                ('pub_date', models.DateTimeField(verbose_name='date published', db_index=True)),
                ('last_edit_time', models.DateTimeField(null=True)),
                ('edit_history', models.TextField(null=True)),
                ('has_attachment', models.BooleanField(default=False, db_index=True)),
                ('has_image', models.BooleanField(default=False, db_index=True)),
                ('has_link', models.BooleanField(default=False, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MitUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(unique=True, max_length=75)),
                ('status', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PreregistrationUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(max_length=75)),
                ('invited_at', models.DateTimeField(auto_now=True)),
                ('status', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PushDeviceToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('kind', models.PositiveSmallIntegerField(choices=[(1, 'apns'), (2, 'gcm')])),
                ('token', models.CharField(unique=True, max_length=4096)),
                ('last_updated', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('ios_app_id', models.TextField(null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Realm',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(unique=True, max_length=40, db_index=True)),
                ('name', models.CharField(max_length=40, null=True)),
                ('restricted_to_domain', models.BooleanField(default=True)),
                ('invite_required', models.BooleanField(default=False)),
                ('invite_by_admins_only', models.BooleanField(default=False)),
                ('mandatory_topics', models.BooleanField(default=False)),
                ('show_digest_email', models.BooleanField(default=True)),
                ('name_changes_disabled', models.BooleanField(default=False)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('deactivated', models.BooleanField(default=False)),
            ],
            options={
                'permissions': (('administer', 'Administer a realm'),),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RealmAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(unique=True, max_length=80, db_index=True)),
                ('realm', models.ForeignKey(to='zerver.Realm', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RealmEmoji',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('img_url', models.TextField()),
                ('realm', models.ForeignKey(to='zerver.Realm')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RealmFilter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('pattern', models.TextField()),
                ('url_format_string', models.TextField()),
                ('realm', models.ForeignKey(to='zerver.Realm')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type_id', models.IntegerField(db_index=True)),
                ('type', models.PositiveSmallIntegerField(db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(max_length=75)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ScheduledJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('scheduled_timestamp', models.DateTimeField()),
                ('type', models.PositiveSmallIntegerField()),
                ('data', models.TextField()),
                ('filter_id', models.IntegerField(null=True)),
                ('filter_string', models.CharField(max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Stream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60, db_index=True)),
                ('invite_only', models.NullBooleanField(default=False)),
                ('email_token', models.CharField(default=zerver.models.generate_email_token_for_stream, max_length=32)),
                ('description', models.CharField(default='', max_length=1024)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('deactivated', models.BooleanField(default=False)),
                ('realm', models.ForeignKey(to='zerver.Realm')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StreamColor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('color', models.CharField(max_length=10)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('active', models.BooleanField(default=True)),
                ('in_home_view', models.NullBooleanField(default=True)),
                ('color', models.CharField(default='#c2c2c2', max_length=10)),
                ('desktop_notifications', models.BooleanField(default=True)),
                ('audible_notifications', models.BooleanField(default=True)),
                ('notifications', models.BooleanField(default=False)),
                ('recipient', models.ForeignKey(to='zerver.Recipient')),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserActivity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('query', models.CharField(max_length=50, db_index=True)),
                ('count', models.IntegerField()),
                ('last_visit', models.DateTimeField(verbose_name='last visit')),
                ('client', models.ForeignKey(to='zerver.Client')),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserActivityInterval',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start', models.DateTimeField(verbose_name='start time', db_index=True)),
                ('end', models.DateTimeField(verbose_name='end time', db_index=True)),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('flags', bitfield.models.BitField(['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned', 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse', 'has_alert_word', 'historical', 'is_me_message'], default=0)),
                ('message', models.ForeignKey(to='zerver.Message')),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserPresence',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField(verbose_name='presence changed')),
                ('status', models.PositiveSmallIntegerField(default=1)),
                ('client', models.ForeignKey(to='zerver.Client')),
                ('user_profile', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='userpresence',
            unique_together=set([('user_profile', 'client')]),
        ),
        migrations.AlterUniqueTogether(
            name='usermessage',
            unique_together=set([('user_profile', 'message')]),
        ),
        migrations.AlterUniqueTogether(
            name='useractivity',
            unique_together=set([('user_profile', 'client', 'query')]),
        ),
        migrations.AlterUniqueTogether(
            name='subscription',
            unique_together=set([('user_profile', 'recipient')]),
        ),
        migrations.AddField(
            model_name='streamcolor',
            name='subscription',
            field=models.ForeignKey(to='zerver.Subscription'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='stream',
            unique_together=set([('name', 'realm')]),
        ),
        migrations.AlterUniqueTogether(
            name='recipient',
            unique_together=set([('type', 'type_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='realmfilter',
            unique_together=set([('realm', 'pattern')]),
        ),
        migrations.AlterUniqueTogether(
            name='realmemoji',
            unique_together=set([('realm', 'name')]),
        ),
        migrations.AddField(
            model_name='realm',
            name='notifications_stream',
            field=models.ForeignKey(related_name='+', blank=True, to='zerver.Stream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='preregistrationuser',
            name='realm',
            field=models.ForeignKey(to='zerver.Realm', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='preregistrationuser',
            name='referred_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='preregistrationuser',
            name='streams',
            field=models.ManyToManyField(to='zerver.Stream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='recipient',
            field=models.ForeignKey(to='zerver.Recipient'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='sender',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='sending_client',
            field=models.ForeignKey(to='zerver.Client'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='defaultstream',
            name='realm',
            field=models.ForeignKey(to='zerver.Realm'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='defaultstream',
            name='stream',
            field=models.ForeignKey(to='zerver.Stream'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='defaultstream',
            unique_together=set([('realm', 'stream')]),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='default_events_register_stream',
            field=models.ForeignKey(related_name='+', to='zerver.Stream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='default_sending_stream',
            field=models.ForeignKey(related_name='+', to='zerver.Stream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='groups',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='realm',
            field=models.ForeignKey(to='zerver.Realm'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='user_permissions',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions'),
            preserve_default=True,
        ),
    ] + zulip_postgres_migrations
