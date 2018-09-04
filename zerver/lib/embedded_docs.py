from django.template import loader
import os

from zerver.models import EmbeddedDocArticle
from zerver.templatetags.app_filters import render_markdown_path

def import_markdown_directory(directory: str) -> None:
    """
    Imports and saves a Markdown subdirectory of `templates` into a database.
    Useful for setting up Postgres-based search of those directories.
    """
    if not directory.endswith("/"):
        directory = directory + "/"
    articles = []
    for entry in os.listdir("templates/" + directory):
        if os.path.isfile("templates/" + directory + entry) and entry.endswith(".md"):
            article_entry = {"directory": directory,
                             "title": entry,
                             "body": render_markdown_path(directory + entry),
                             }
            articles.append(article_entry)
    for article in articles:
        EmbeddedDocArticle.objects.update_or_create(directory=article['directory'],
                                                    title=article['title'],
                                                    defaults=article)
