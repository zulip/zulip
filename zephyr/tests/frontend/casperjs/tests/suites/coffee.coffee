"A small subset of the run.js written in coffeescript"

steps = 0

casper.options.onStepComplete = -> steps++

casper.start "tests/site/index.html", ->
  @test.assertTitle "CasperJS test index", "Casper.start() casper can start itself an open an url"
  @test.assertEquals @fetchText("ul li"), "onetwothree", "Casper.fetchText() can retrieves text contents"
  @click "a[href=\"test.html\"]"

casper.then ->
  @test.assertTitle "CasperJS test target", "Casper.click() casper can click on a text link"
  @click "a[href=\"form.html\"]"

casper.run ->
  @test.assertEquals steps, 3, "Casper.options.onStepComplete() is called on step complete"
  @options.onStepComplete = null
  @test.done(4)
