from scrapy.commands.crawl import Command
from scrapy.exceptions import UsageError
from typing import List, Any


class StatusCommand(Command):
    def run(self, args: List[str], opts: Any) -> None:
        if len(args) < 1:
            raise UsageError()
        elif len(args) > 1:
            raise UsageError(
                "running 'scrapy crawl' with more than one spider is no longer supported")
        spname = args[0]
        if len(vars(opts)['spargs']) > 0:
            skip_external = vars(opts)['spargs']['skip_external']
        else:
            skip_external = None
        crawler = self.crawler_process.create_crawler(spname)
        self.crawler_process.crawl(crawler, skip_external=skip_external)
        self.crawler_process.start()
        if crawler.stats.get_value("log_count/ERROR"):
            self.exitcode = 1
