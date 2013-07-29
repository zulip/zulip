# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Realm'
        db.create_table(u'zephyr_realm', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40, db_index=True)),
            ('restricted_to_domain', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'zephyr', ['Realm'])

        # Adding model 'UserProfile'
        db.create_table(u'zephyr_userprofile', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('last_login', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('is_staff', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('date_joined', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('full_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('short_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('pointer', self.gf('django.db.models.fields.IntegerField')()),
            ('last_pointer_updater', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('realm', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Realm'])),
            ('api_key', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('enable_desktop_notifications', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('enter_sends', self.gf('django.db.models.fields.NullBooleanField')(default=False, null=True, blank=True)),
        ))
        db.send_create_signal(u'zephyr', ['UserProfile'])

        # Adding model 'PreregistrationUser'
        db.create_table(u'zephyr_preregistrationuser', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('referred_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'], null=True)),
            ('invited_at', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'zephyr', ['PreregistrationUser'])

        # Adding M2M table for field streams on 'PreregistrationUser'
        db.create_table(u'zephyr_preregistrationuser_streams', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('preregistrationuser', models.ForeignKey(orm[u'zephyr.preregistrationuser'], null=False)),
            ('stream', models.ForeignKey(orm[u'zephyr.stream'], null=False))
        ))
        db.create_unique(u'zephyr_preregistrationuser_streams', ['preregistrationuser_id', 'stream_id'])

        # Adding model 'MitUser'
        db.create_table(u'zephyr_mituser', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(unique=True, max_length=75)),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'zephyr', ['MitUser'])

        # Adding model 'Stream'
        db.create_table(u'zephyr_stream', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=30, db_index=True)),
            ('realm', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Realm'])),
            ('invite_only', self.gf('django.db.models.fields.NullBooleanField')(default=False, null=True, blank=True)),
        ))
        db.send_create_signal(u'zephyr', ['Stream'])

        # Adding unique constraint on 'Stream', fields ['name', 'realm']
        db.create_unique(u'zephyr_stream', ['name', 'realm_id'])

        # Adding model 'Recipient'
        db.create_table(u'zephyr_recipient', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('type_id', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(db_index=True)),
        ))
        db.send_create_signal(u'zephyr', ['Recipient'])

        # Adding unique constraint on 'Recipient', fields ['type', 'type_id']
        db.create_unique(u'zephyr_recipient', ['type', 'type_id'])

        # Adding model 'Client'
        db.create_table(u'zephyr_client', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=30, db_index=True)),
        ))
        db.send_create_signal(u'zephyr', ['Client'])

        # Adding model 'Message'
        db.create_table(u'zephyr_message', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('sender', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'])),
            ('recipient', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Recipient'])),
            ('subject', self.gf('django.db.models.fields.CharField')(max_length=60, db_index=True)),
            ('content', self.gf('django.db.models.fields.TextField')()),
            ('rendered_content', self.gf('django.db.models.fields.TextField')(null=True)),
            ('rendered_content_version', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('pub_date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('sending_client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Client'])),
        ))
        db.send_create_signal(u'zephyr', ['Message'])

        # Adding model 'UserMessage'
        db.create_table(u'zephyr_usermessage', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_profile', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'])),
            ('message', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Message'])),
            ('archived', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('flags', self.gf('django.db.models.fields.BigIntegerField')(default=0)),
        ))
        db.send_create_signal(u'zephyr', ['UserMessage'])

        # Adding unique constraint on 'UserMessage', fields ['user_profile', 'message']
        db.create_unique(u'zephyr_usermessage', ['user_profile_id', 'message_id'])

        # Adding model 'Subscription'
        db.create_table(u'zephyr_subscription', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_profile', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'])),
            ('recipient', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Recipient'])),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('in_home_view', self.gf('django.db.models.fields.NullBooleanField')(default=True, null=True, blank=True)),
        ))
        db.send_create_signal(u'zephyr', ['Subscription'])

        # Adding unique constraint on 'Subscription', fields ['user_profile', 'recipient']
        db.create_unique(u'zephyr_subscription', ['user_profile_id', 'recipient_id'])

        # Adding model 'Huddle'
        db.create_table(u'zephyr_huddle', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('huddle_hash', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40, db_index=True)),
        ))
        db.send_create_signal(u'zephyr', ['Huddle'])

        # Adding model 'UserActivity'
        db.create_table(u'zephyr_useractivity', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_profile', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'])),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Client'])),
            ('query', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('count', self.gf('django.db.models.fields.IntegerField')()),
            ('last_visit', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'zephyr', ['UserActivity'])

        # Adding unique constraint on 'UserActivity', fields ['user_profile', 'client', 'query']
        db.create_unique(u'zephyr_useractivity', ['user_profile_id', 'client_id', 'query'])

        # Adding model 'UserPresence'
        db.create_table(u'zephyr_userpresence', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_profile', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.UserProfile'])),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Client'])),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')()),
            ('status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1)),
        ))
        db.send_create_signal(u'zephyr', ['UserPresence'])

        # Adding unique constraint on 'UserPresence', fields ['user_profile', 'client']
        db.create_unique(u'zephyr_userpresence', ['user_profile_id', 'client_id'])

        # Adding model 'DefaultStream'
        db.create_table(u'zephyr_defaultstream', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('realm', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Realm'])),
            ('stream', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Stream'])),
        ))
        db.send_create_signal(u'zephyr', ['DefaultStream'])

        # Adding unique constraint on 'DefaultStream', fields ['realm', 'stream']
        db.create_unique(u'zephyr_defaultstream', ['realm_id', 'stream_id'])

        # Adding model 'StreamColor'
        db.create_table(u'zephyr_streamcolor', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('subscription', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['zephyr.Subscription'])),
            ('color', self.gf('django.db.models.fields.CharField')(max_length=10)),
        ))
        db.send_create_signal(u'zephyr', ['StreamColor'])

        if "postgres" not in settings.DATABASES["default"]["ENGINE"]:
            return
        # we do not populate search_tsvector, as the data which you'd normally populate it is empty (which would be a NO-OP).
        # Also, we populate it in a later migration.
        db.execute("ALTER TABLE zephyr_message ADD COLUMN search_tsvector tsvector")
        if len(db.execute("""SELECT relname FROM pg_class
                             WHERE relname = 'zephyr_message_search_tsvector'""")) != 0:
            print "Not creating index because it already exists"
        else:
            db.execute("""CREATE INDEX zephyr_message_search_tsvector ON zephyr_message
                          USING gin(search_tsvector)""")
        db.execute("""CREATE TRIGGER zephyr_message_update_search_tsvector
                      BEFORE INSERT OR UPDATE ON zephyr_message FOR EACH ROW
                      EXECUTE PROCEDURE tsvector_update_trigger(search_tsvector,
                      'pg_catalog.english', subject, content)""");

    def backwards(self, orm):
        # Removing unique constraint on 'DefaultStream', fields ['realm', 'stream']
        db.delete_unique(u'zephyr_defaultstream', ['realm_id', 'stream_id'])

        # Removing unique constraint on 'UserPresence', fields ['user_profile', 'client']
        db.delete_unique(u'zephyr_userpresence', ['user_profile_id', 'client_id'])

        # Removing unique constraint on 'UserActivity', fields ['user_profile', 'client', 'query']
        db.delete_unique(u'zephyr_useractivity', ['user_profile_id', 'client_id', 'query'])

        # Removing unique constraint on 'Subscription', fields ['user_profile', 'recipient']
        db.delete_unique(u'zephyr_subscription', ['user_profile_id', 'recipient_id'])

        # Removing unique constraint on 'UserMessage', fields ['user_profile', 'message']
        db.delete_unique(u'zephyr_usermessage', ['user_profile_id', 'message_id'])

        # Removing unique constraint on 'Recipient', fields ['type', 'type_id']
        db.delete_unique(u'zephyr_recipient', ['type', 'type_id'])

        # Removing unique constraint on 'Stream', fields ['name', 'realm']
        db.delete_unique(u'zephyr_stream', ['name', 'realm_id'])

        # Deleting model 'Realm'
        db.delete_table(u'zephyr_realm')

        # Deleting model 'UserProfile'
        db.delete_table(u'zephyr_userprofile')

        # Deleting model 'PreregistrationUser'
        db.delete_table(u'zephyr_preregistrationuser')

        # Removing M2M table for field streams on 'PreregistrationUser'
        db.delete_table('zephyr_preregistrationuser_streams')

        # Deleting model 'MitUser'
        db.delete_table(u'zephyr_mituser')

        # Deleting model 'Stream'
        db.delete_table(u'zephyr_stream')

        # Deleting model 'Recipient'
        db.delete_table(u'zephyr_recipient')

        # Deleting model 'Client'
        db.delete_table(u'zephyr_client')

        # Deleting model 'Message'
        db.delete_table(u'zephyr_message')

        # Deleting model 'UserMessage'
        db.delete_table(u'zephyr_usermessage')

        # Deleting model 'Subscription'
        db.delete_table(u'zephyr_subscription')

        # Deleting model 'Huddle'
        db.delete_table(u'zephyr_huddle')

        # Deleting model 'UserActivity'
        db.delete_table(u'zephyr_useractivity')

        # Deleting model 'UserPresence'
        db.delete_table(u'zephyr_userpresence')

        # Deleting model 'DefaultStream'
        db.delete_table(u'zephyr_defaultstream')

        # Deleting model 'StreamColor'
        db.delete_table(u'zephyr_streamcolor')


    models = {
        u'zephyr.client': {
            'Meta': {'object_name': 'Client'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30', 'db_index': 'True'})
        },
        u'zephyr.defaultstream': {
            'Meta': {'unique_together': "(('realm', 'stream'),)", 'object_name': 'DefaultStream'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Realm']"}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Stream']"})
        },
        u'zephyr.huddle': {
            'Meta': {'object_name': 'Huddle'},
            'huddle_hash': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'zephyr.message': {
            'Meta': {'object_name': 'Message'},
            'content': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Recipient']"}),
            'rendered_content': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'rendered_content_version': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'sender': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']"}),
            'sending_client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Client']"}),
            'subject': ('django.db.models.fields.CharField', [], {'max_length': '60', 'db_index': 'True'})
        },
        u'zephyr.mituser': {
            'Meta': {'object_name': 'MitUser'},
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'zephyr.preregistrationuser': {
            'Meta': {'object_name': 'PreregistrationUser'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invited_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'referred_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']", 'null': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'streams': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['zephyr.Stream']", 'null': 'True', 'symmetrical': 'False'})
        },
        u'zephyr.realm': {
            'Meta': {'object_name': 'Realm'},
            'domain': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'restricted_to_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'zephyr.recipient': {
            'Meta': {'unique_together': "(('type', 'type_id'),)", 'object_name': 'Recipient'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'db_index': 'True'}),
            'type_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        u'zephyr.stream': {
            'Meta': {'unique_together': "(('name', 'realm'),)", 'object_name': 'Stream'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invite_only': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'db_index': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Realm']"})
        },
        u'zephyr.streamcolor': {
            'Meta': {'object_name': 'StreamColor'},
            'color': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Subscription']"})
        },
        u'zephyr.subscription': {
            'Meta': {'unique_together': "(('user_profile', 'recipient'),)", 'object_name': 'Subscription'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_home_view': ('django.db.models.fields.NullBooleanField', [], {'default': 'True', 'null': 'True', 'blank': 'True'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Recipient']"}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']"})
        },
        u'zephyr.useractivity': {
            'Meta': {'unique_together': "(('user_profile', 'client', 'query'),)", 'object_name': 'UserActivity'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Client']"}),
            'count': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_visit': ('django.db.models.fields.DateTimeField', [], {}),
            'query': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']"})
        },
        u'zephyr.usermessage': {
            'Meta': {'unique_together': "(('user_profile', 'message'),)", 'object_name': 'UserMessage'},
            'archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'flags': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Message']"}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']"})
        },
        u'zephyr.userpresence': {
            'Meta': {'unique_together': "(('user_profile', 'client'),)", 'object_name': 'UserPresence'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Client']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']"})
        },
        u'zephyr.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'api_key': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'enable_desktop_notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enter_sends': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'full_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_pointer_updater': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'pointer': ('django.db.models.fields.IntegerField', [], {}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Realm']"}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['zephyr']
