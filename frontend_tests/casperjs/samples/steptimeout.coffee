failed = []
start = null
links = [
    "http://google.com/"
    "http://akei.com/"
    "http://lemonde.fr/"
    "http://liberation.fr/"
    "http://cdiscount.fr/"
]

casper = require("casper").create
    onStepTimeout: ->
        failed.push @requestUrl
        @test.fail "#{@requestUrl} loads in less than #{timeout}ms."

casper.on "load.finished", ->
    @echo "#{@requestUrl} loaded in #{new Date() - start}ms", "PARAMETER"

timeout = ~~casper.cli.get(0)
timeout = 1000 if timeout < 1
casper.options.stepTimeout = timeout

casper.echo "Testing with timeout=#{timeout}ms, please be patient."

casper.start()

casper.each links, (self, link) ->
    @then ->
        @test.comment "Loading #{link}"
        start = new Date()
        @open link
    @then ->
        if @requestUrl not in failed
            @test.pass "#{@requestUrl} loaded in less than #{timeout}ms."

casper.run ->
    @test.renderResults true
