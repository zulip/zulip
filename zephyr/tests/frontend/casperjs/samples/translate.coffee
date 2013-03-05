###
Translation using the Google Translate Service.

Usage:

$ casperjs translate.coffee --target=fr "hello world"
bonjour tout le monde
###
system = require("system")
casper = require("casper").create()
format = require("utils").format
source = casper.cli.get("source") or "auto"
target = casper.cli.get("target")
text = casper.cli.get(0)
result = undefined

casper.warn("The --target option is mandatory.").exit 1  unless target

casper.start(format("http://translate.google.com/#%s/%s/%s", source, target, text), ->
  @fill "form#gt-form", text: text
).waitForSelector "span.hps", -> @echo @fetchText("#result_box")

casper.run()
