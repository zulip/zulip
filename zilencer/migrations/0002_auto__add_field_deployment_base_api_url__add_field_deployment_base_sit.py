# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Deployment.base_api_url'
        db.add_column(u'zilencer_deployment', 'base_api_url',
                self.gf('django.db.models.fields.CharField')(default='https://api.zulip.com/', max_length=128),
                      keep_default=False)

        # Adding field 'Deployment.base_site_url'
        db.add_column(u'zilencer_deployment', 'base_site_url',
                self.gf('django.db.models.fields.CharField')(default='https://zulip.com/', max_length=128),
                      keep_default=False)
        try:
            # Defaults for the zulip.com internal realm
            dep = orm['zilencer.Deployment'].objects.get(realms__domain="zulip.com")
            dep.base_api_url = "https://staging.zulip.com/api/"
            dep.base_site_url = "https://staging.zulip.com/"
            dep.save()
        except orm['zilencer.Deployment'].DoesNotExist:
            pass


    def backwards(self, orm):
        # Deleting field 'Deployment.base_api_url'
        db.delete_column(u'zilencer_deployment', 'base_api_url')

        # Deleting field 'Deployment.base_site_url'
        db.delete_column(u'zilencer_deployment', 'base_site_url')


    models = {
        u'zerver.realm': {
            'Meta': {'object_name': 'Realm'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'domain': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'notifications_stream': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': u"orm['zerver.Stream']"}),
            'restricted_to_domain': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'zerver.stream': {
            'Meta': {'unique_together': "(('name', 'realm'),)", 'object_name': 'Stream'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email_token': ('django.db.models.fields.CharField', [], {'default': "'a647d6a6aefc21a71dc12339c184d6a2'", 'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invite_only': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60', 'db_index': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"})
        },
        u'zilencer.deployment': {
            'Meta': {'object_name': 'Deployment'},
            'api_key': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'base_api_url': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'base_site_url': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'realms': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'_deployments'", 'symmetrical': 'False', 'to': u"orm['zerver.Realm']"})
        }
    }

    complete_apps = ['zilencer']
