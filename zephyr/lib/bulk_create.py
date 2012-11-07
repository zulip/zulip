from django.conf import settings
# batch_bulk_create should become obsolete with Django 1.5, when the
# Django bulk_create method accepts a batch_size directly.
def batch_bulk_create(cls, cls_list, batch_size=150):
    if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
        # We don't need a low batch size with mysql, but we do need
        # one to avoid "MySQL Server has gone away" errors
        batch_size = 2000
    while len(cls_list) > 0:
        current_batch = cls_list[0:batch_size]
        cls.objects.bulk_create(current_batch)
        cls_list = cls_list[batch_size:]
