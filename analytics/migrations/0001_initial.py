# -*- coding: utf-8 -*-
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0030_realm_org_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Anomaly',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('info', models.CharField(max_length=1000)),
            ],
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HuddleCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('huddle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Recipient')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('property', models.CharField(max_length=40)),
                ('end_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('value', models.BigIntegerField()),
                ('anomaly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analytics.Anomaly', null=True)),
            ],
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InstallationCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('property', models.CharField(max_length=40)),
                ('end_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('value', models.BigIntegerField()),
                ('anomaly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analytics.Anomaly', null=True)),
            ],
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RealmCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm')),
                ('property', models.CharField(max_length=40)),
                ('end_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('value', models.BigIntegerField()),
                ('anomaly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analytics.Anomaly', null=True)),

            ],
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StreamCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm')),
                ('stream', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Stream')),
                ('property', models.CharField(max_length=40)),
                ('end_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('value', models.BigIntegerField()),
                ('anomaly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analytics.Anomaly', null=True)),
            ],
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('property', models.CharField(max_length=40)),
                ('end_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('value', models.BigIntegerField()),
                ('anomaly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='analytics.Anomaly', null=True)),
            ],
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='usercount',
            unique_together=set([('user', 'property', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='streamcount',
            unique_together=set([('stream', 'property', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='realmcount',
            unique_together=set([('realm', 'property', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='installationcount',
            unique_together=set([('property', 'end_time', 'interval')]),
        ),
        migrations.AlterUniqueTogether(
            name='huddlecount',
            unique_together=set([('huddle', 'property', 'end_time', 'interval')]),
        ),
    ]
