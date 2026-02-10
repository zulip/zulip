import argparse

from scrapy.commands import crawl
from scrapy.crawler import Crawler
from scrapy.spiders import Spider
from typing_extensions import override


class Command(crawl.Command):
    @override
    def run(self, args: list[str], opts: argparse.Namespace) -> None:
        crawlers = []
        assert self.crawler_process is not None
        real_create_crawler = self.crawler_process.create_crawler

        def create_crawler(crawler_or_spidercls: type[Spider] | Crawler | str) -> Crawler:
            crawler = real_create_crawler(crawler_or_spidercls)
            crawlers.append(crawler)
            return crawler

        self.crawler_process.create_crawler = create_crawler  # type: ignore[method-assign]  # monkey patching
        super().run(args, opts)
        for crawler in crawlers:
            assert crawler.stats is not None
            if crawler.stats.get_value("log_count/ERROR"):
                self.exitcode = 1
