from django.conf import settings
from django.contrib.staticfiles.finders import AppDirectoriesFinder

class ExcludeMinifiedMixin(object):
    def list(self, ignore_patterns):
        # We can't use ignore_patterns because the patterns are
        # applied to just the file part, not the entire path
        to_exclude = set()
        for collection in (settings.PIPELINE_CSS, settings.PIPELINE_JS):
            for key in collection:
                to_exclude.update(collection[key]['source_filenames'])

        super_class = super(ExcludeMinifiedMixin, self)
        for path, storage in super_class.list(ignore_patterns):
            if not path in to_exclude:
                yield path, storage

class HumbugFinder(ExcludeMinifiedMixin, AppDirectoriesFinder):
    pass
