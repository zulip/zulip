from scrapy.commands.crawl import Command
from scrapy.exceptions import UsageError
from typing import List, Any


class StatusCommand(Command):
    def run(self, args, opts):
        # type: (List[str], Any) -> None
        if len(args) < 1:
            raise UsageError()
        elif len(args) > 1:
            raise UsageError(
                "running 'scrapy crawl' with more than one spider is no longer supported")
        spname = args[0]

        crawler = self.crawler_process.create_crawler(spname)
        self.crawler_process.crawl(crawler)
        self.crawler_process.start()
        # Get exceptions quantity from crawler stat data
        stats = crawler.stats.get_stats()
        error_404 = 'downloader/response_status_count/404'
        error_io = 'downloader/exception_type_count/exceptions.IOError'
        if stats.get(error_404) or stats.get(error_io):
            # Return non-zero exit code if exceptions are contained
            self.exitcode = 1
