from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodlRegistrationPin",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pin_hash", models.CharField(max_length=255)),
                ("failed_attempts", models.IntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nodl_registration_pin",
                        to="zerver.userprofile",
                    ),
                ),
            ],
            options={
                "db_table": "nodl_registration_pin",
            },
        ),
    ]
