###
Takes provided terms passed as arguments and query google for the number of
estimated results each have.

Usage:
    $ casperjs googlematch.coffee nicolas chuck borris
    nicolas: 69600000
    chuck:   49500000
    borris:  2370000
    winner is "nicolas" with 69600000 results
###

casper = require("casper").create verbose: true

casper.fetchScore = ->
    @evaluate ->
        result = __utils__.findOne('#resultStats').innerText
        parseInt /Environ ([0-9\s]{1,}).*/.exec(result)[1].replace(/\s/g, '')

terms = casper.cli.args # terms are passed through command-line arguments

if terms.length < 2
    casper
        .echo("Usage: $ casperjs googlematch.js term1 term2 [term3]...")
        .exit(1)

scores = []

casper.echo "Let the match begin between \"#{terms.join '", "'}\"!"

casper.start "http://google.fr/"

casper.each terms, (self, term) ->
    @then -> @fill 'form[action="/search"]', { q: term }, true
    @then ->
        score = @fetchScore()
        scores.push term: term, score: score
        @echo "#{term}: #{score}"

casper.run ->
    if scores.length is 0
        @echo "No result found"
    else
        scores.sort (a, b) -> b.score - a.score
        winner = scores[0]
        @echo "Winner is \"" + winner.term + "\" with " + winner.score + " results"
  @exit()
