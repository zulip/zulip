step = 0

# testing resources
casper.start "tests/site/resources.html", ->
  @test.assertEquals ++step, 1, "step 1"
  @wait 400, ->
    @test.assertEquals ++step, 2, "step 1.1"
    @wait 200, ->
      @test.assertEquals ++step, 3, "step 1.1.1"
      @wait 200, ->
        @test.assertEquals ++step, 4, "step 1.1.1.1"
    @then ->
      @test.assertEquals ++step, 5, "step 1.1.2.1"
  @wait 400, ->
    @test.assertEquals ++step, 6, "step 1.2"

casper.wait 200, ->
  @test.assertEquals ++step, 7, "step 2"

casper.waitForSelector(
  '#noneExistingSelector'
  -> @test.fail "should run into timeout"
  -> @test.assertEquals ++step, 8, "step 3 sucessfully timed out"
  1000
)
casper.then ->
  @test.assertEquals ++step, 9, "step 4"
  @wait 300, ->
    @test.assertEquals ++step, 10, "step 4.1"
    @wait 300, ->
      @test.assertEquals ++step, 11, "step 4.1.1"
  @wait 100, ->
    @test.assertEquals ++step, 12, "step 5.2"

casper.then ->
  @test.assertEquals ++step, 13, "last step"

casper.run(-> @test.done(13))
