# Generated manually for whisper chat feature

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0753_remove_google_blob_emojiset'),
    ]

    operations = [
        # Add whisper_conversation field to AbstractMessage (affects Message and ArchivedMessage)
        migrations.AddField(
            model_name='message',
            name='whisper_conversation',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='zerver.whisperconversation'
            ),
        ),
        migrations.AddField(
            model_name='archivedmessage',
            name='whisper_conversation',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='zerver.whisperconversation'
            ),
        ),
        
        # Add parent_recipient field to Recipient model
        migrations.AddField(
            model_name='recipient',
            name='parent_recipient',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='whisper_recipients',
                to='zerver.recipient'
            ),
        ),
        
        # Create WhisperConversation model
        migrations.CreateModel(
            name='WhisperConversation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('participants_hash', models.CharField(db_index=True, max_length=40)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.userprofile')),
                ('parent_recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='whisper_conversations', to='zerver.recipient')),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.realm')),
            ],
        ),
        
        # Create WhisperRequest model
        migrations.CreateModel(
            name='WhisperRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('status', models.PositiveSmallIntegerField(choices=[(1, 'Pending'), (2, 'Accepted'), (3, 'Declined'), (4, 'Expired')], db_index=True, default=1)),
                ('parent_recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.recipient')),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.realm')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_whisper_requests', to='zerver.userprofile')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_whisper_requests', to='zerver.userprofile')),
                ('whisper_conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='zerver.whisperconversation')),
            ],
        ),
        
        # Create WhisperParticipant model
        migrations.CreateModel(
            name='WhisperParticipant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('left_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.userprofile')),
                ('whisper_conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.whisperconversation')),
            ],
        ),
        
        # Add indexes for WhisperConversation
        migrations.AddIndex(
            model_name='whisperconversation',
            index=models.Index(fields=['realm', 'parent_recipient', 'is_active'], name='zerver_whisperconversation_realm_parent_active'),
        ),
        migrations.AddIndex(
            model_name='whisperconversation',
            index=models.Index(fields=['participants_hash', 'is_active'], name='zerver_whisperconversation_hash_active'),
        ),
        
        # Add indexes for WhisperRequest
        migrations.AddIndex(
            model_name='whisperrequest',
            index=models.Index(fields=['recipient', 'status'], name='zerver_whisperrequest_recipient_status'),
        ),
        migrations.AddIndex(
            model_name='whisperrequest',
            index=models.Index(fields=['requester', 'status'], name='zerver_whisperrequest_requester_status'),
        ),
        migrations.AddIndex(
            model_name='whisperrequest',
            index=models.Index(fields=['realm', 'created_at'], name='zerver_whisperrequest_realm_created'),
        ),
        
        # Add indexes for WhisperParticipant
        migrations.AddIndex(
            model_name='whisperparticipant',
            index=models.Index(fields=['whisper_conversation', 'is_active'], name='zerver_whisperparticipant_conversation_active'),
        ),
        migrations.AddIndex(
            model_name='whisperparticipant',
            index=models.Index(fields=['user_profile', 'is_active'], name='zerver_whisperparticipant_user_active'),
        ),
        
        # Add unique constraints
        migrations.AlterUniqueTogether(
            name='whisperrequest',
            unique_together={('requester', 'recipient', 'parent_recipient', 'whisper_conversation')},
        ),
        migrations.AlterUniqueTogether(
            name='whisperparticipant',
            unique_together={('whisper_conversation', 'user_profile')},
        ),
    ]