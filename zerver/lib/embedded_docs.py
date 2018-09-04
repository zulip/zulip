from django.template import loader
import os

from zerver.models import EmbeddedDocArticle
from zerver.templatetags.app_filters import render_markdown_path

def import_markdown_directory(directory: str) -> None:
    """
    Imports and saves a Markdown subdirectory of `templates` into a database.
    Useful for setting up Postgres-based search of those directories.
    """
    articles = []
    for entry in os.listdir("templates/" + directory):
        if os.path.isfile("templates/" + directory + entry) and entry.endswith(".md"):
            article_entry = {"directory": directory,
                             "title": entry,
                             "body": render_markdown_path(directory + entry),
                             }
            articles.append(EmbeddedDocArticle(**article_entry))
    EmbeddedDocArticle.objects.bulk_create(articles)
