# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Deployment'
        db.create_table(u'zilencer_deployment', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('api_key', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
        ))
        db.send_create_signal(u'zilencer', ['Deployment'])

        # Adding M2M table for field realms on 'Deployment'
        db.create_table(u'zilencer_deployment_realms', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('deployment', models.ForeignKey(orm[u'zilencer.deployment'], null=False)),
            ('realm', models.ForeignKey(orm[u'zerver.realm'], null=False))
        ))
        db.create_unique(u'zilencer_deployment_realms', ['deployment_id', 'realm_id'])

        if not settings.ENTERPRISE:
            try:
                dep = orm['zilencer.Deployment']()
                dep.api_key = settings.DEPLOYMENT_ROLE_KEY
                dep.save()
                dep.realms = [orm['zerver.Realm'].objects.get(domain="zulip.com")]
                dep.save()

                dep = orm['zilencer.Deployment']()
                dep.api_key = settings.DEPLOYMENT_ROLE_KEY
                dep.save()
                dep.realms = orm['zerver.Realm'].objects.annotate(dc=models.Count("_deployments")).filter(dc=0)
                dep.save()
            except orm['zerver.Realm'].DoesNotExist:
                pass



    def backwards(self, orm):
        # Deleting model 'Deployment'
        db.delete_table(u'zilencer_deployment')

        # Removing M2M table for field realms on 'Deployment'
        db.delete_table('zilencer_deployment_realms')


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
            'email_token': ('django.db.models.fields.CharField', [], {'default': "'1946c400b4b841499b527216b8bc3db6'", 'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invite_only': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60', 'db_index': 'True'}),
            'realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['zerver.Realm']"})
        },
        u'zilencer.deployment': {
            'Meta': {'object_name': 'Deployment'},
            'api_key': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'realms': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'_deployments'", 'symmetrical': 'False', 'to': u"orm['zerver.Realm']"})
        }
    }

    complete_apps = ['zilencer']
