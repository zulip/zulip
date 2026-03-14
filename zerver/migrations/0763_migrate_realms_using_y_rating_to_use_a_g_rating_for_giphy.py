from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def use_a_g_rating_instead_of_y_rating(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    # Apparently, GIPHY removed the "Y" rating at some point; so we
    # need to consolidate/collapse our rating level configuration. We
    # round "Y" to the nearest remaining value, "G".
    #
    # The previous mapping was 1->Y, 2->G, 3->PG, 4->PG-13, 5->R
    # We now shift that to 1->G, 2->PG, 3->PG-13, 4->R
    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.filter(giphy_rating__gte=2).update(giphy_rating=models.F("giphy_rating") - 1)


class Migration(migrations.Migration):
    dependencies = [("zerver", "0762_realm_owner_full_content_access")]
    operations = [
        migrations.RunPython(use_a_g_rating_instead_of_y_rating),
        migrations.AlterField(
            model_name="realm",
            name="giphy_rating",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
