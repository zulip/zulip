# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Realm.name'
        db.add_column(u'zerver_realm', 'name',
                      self.gf('django.db.models.fields.CharField')(max_length=40, null=True),
                      keep_default=True)


    def backwards(self, orm):
        # Deleting field 'Realm.name'
        db.delete_column(u'zerver_realm', 'name')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'zerver.appledevicetoken': {
            'Meta': {'object_name': 'AppleDeviceToken'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.client': {
            'Meta': {'object_name': 'Client'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30', 'db_index': 'True'})
        },
        u'zerver.defaultstream': {
            'Meta': {'unique_together': "(('realm', 'stream'),)", 'object_name': 'DefaultStream'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Stream']"})
        },
        u'zerver.huddle': {
            'Meta': {'object_name': 'Huddle'},
            'huddle_hash': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'zerver.message': {
            'Meta': {'object_name': 'Message'},
            'content': ('django.db.models.fields.TextField', [], {}),
            'edit_history': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_edit_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'pub_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Recipient']"}),
            'rendered_content': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'rendered_content_version': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'sender': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"}),
            'sending_client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Client']"}),
            'subject': ('django.db.models.fields.CharField', [], {'max_length': '60', 'db_index': 'True'})
        },
        u'zerver.mituser': {
            'Meta': {'object_name': 'MitUser'},
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'zerver.preregistrationuser': {
            'Meta': {'object_name': 'PreregistrationUser'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invited_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']", 'null': 'True'}),
            'referred_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']", 'null': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'streams': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['zerver.Stream']", 'null': 'True', 'symmetrical': 'False'})
        },
        u'zerver.realm': {
            'Meta': {'object_name': 'Realm'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'domain': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'notifications_stream': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': u"orm['zerver.Stream']"}),
            'restricted_to_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'zerver.realmemoji': {
            'Meta': {'unique_together': "(('realm', 'name'),)", 'object_name': 'RealmEmoji'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.TextField', [], {}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"})
        },
        u'zerver.recipient': {
            'Meta': {'unique_together': "(('type', 'type_id'),)", 'object_name': 'Recipient'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'db_index': 'True'}),
            'type_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        u'zerver.referral': {
            'Meta': {'object_name': 'Referral'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.stream': {
            'Meta': {'unique_together': "(('name', 'realm'),)", 'object_name': 'Stream'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email_token': ('django.db.models.fields.CharField', [], {'default': "'b83fa08f8298ddd4f39e8af24296440e'", 'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invite_only': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60', 'db_index': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"})
        },
        u'zerver.streamcolor': {
            'Meta': {'object_name': 'StreamColor'},
            'color': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Subscription']"})
        },
        u'zerver.subscription': {
            'Meta': {'unique_together': "(('user_profile', 'recipient'),)", 'object_name': 'Subscription'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'color': ('django.db.models.fields.CharField', [], {'default': "'#c2c2c2'", 'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_home_view': ('django.db.models.fields.NullBooleanField', [], {'default': 'True', 'null': 'True', 'blank': 'True'}),
            'notifications': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Recipient']"}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.useractivity': {
            'Meta': {'unique_together': "(('user_profile', 'client', 'query'),)", 'object_name': 'UserActivity'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Client']"}),
            'count': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_visit': ('django.db.models.fields.DateTimeField', [], {}),
            'query': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.useractivityinterval': {
            'Meta': {'object_name': 'UserActivityInterval'},
            'end': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.usermessage': {
            'Meta': {'unique_together': "(('user_profile', 'message'),)", 'object_name': 'UserMessage'},
            'archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'flags': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Message']"}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.userpresence': {
            'Meta': {'unique_together': "(('user_profile', 'client'),)", 'object_name': 'UserPresence'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Client']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'user_profile': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']"})
        },
        u'zerver.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'alert_words': ('django.db.models.fields.TextField', [], {'default': "'[]'"}),
            'api_key': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'avatar_source': ('django.db.models.fields.CharField', [], {'default': "'G'", 'max_length': '1'}),
            'bot_owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.UserProfile']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'db_index': 'True'}),
            'enable_desktop_notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_offline_email_notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_sounds': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enter_sends': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'full_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invites_granted': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'invites_used': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_bot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_pointer_updater': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'last_reminder': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True'}),
            'muted_topics': ('django.db.models.fields.TextField', [], {'default': "'[]'"}),
            'onboarding_steps': ('django.db.models.fields.TextField', [], {'default': "'[]'"}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'pointer': ('django.db.models.fields.IntegerField', [], {}),
            'rate_limits': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'tutorial_status': ('django.db.models.fields.CharField', [], {'default': "'W'", 'max_length': '1'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        }
    }

    complete_apps = ['zerver']
