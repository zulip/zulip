# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        db.execute("DROP INDEX IF EXISTS zephyr_message_full_text_idx")

    def backwards(self, orm):
        pass

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
            'edit_history': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_edit_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
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
            'color': ('django.db.models.fields.CharField', [], {'default': "'#c2c2c2'", 'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_home_view': ('django.db.models.fields.NullBooleanField', [], {'default': 'True', 'null': 'True', 'blank': 'True'}),
            'notifications': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'avatar_source': ('django.db.models.fields.CharField', [], {'default': "'G'", 'max_length': '1'}),
            'bot_owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.UserProfile']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'db_index': 'True'}),
            'enable_desktop_notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_offline_email_notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_sounds': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enter_sends': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'full_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_bot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_pointer_updater': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'last_reminder': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True'}),
            'onboarding_steps': ('django.db.models.fields.TextField', [], {'default': "'[]'"}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'pointer': ('django.db.models.fields.IntegerField', [], {}),
            'rate_limits': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zephyr.Realm']"}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'tutorial_status': ('django.db.models.fields.CharField', [], {'default': "'W'", 'max_length': '1'})
        }
    }

    complete_apps = ['zephyr']
