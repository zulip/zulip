from django.conf import settings
# batch_bulk_create should become obsolete with Django 1.5, when the
# Django bulk_create method accepts a batch_size directly.
def batch_bulk_create(cls, cls_list, batch_size=150):
    if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
        # We only need to do the below batching nonsense with sqlite.
        cls.objects.bulk_create(cls_list)
        return
    while len(cls_list) > 0:
        current_batch = cls_list[0:batch_size]
        cls.objects.bulk_create(current_batch)
        cls_list = cls_list[batch_size:]
