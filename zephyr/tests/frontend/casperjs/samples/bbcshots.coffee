###
Create a mosaic image from all headline photos on BBC homepage
###

casper = require("casper").create()
nbLinks = 0
currentLink = 1
images = []

# helper to hide some element from remote DOM
casper.hide = (selector) ->
    @evaluate (selector) ->
        document.querySelector(selector).style.display = "none"
    , selector

casper.start "http://www.bbc.co.uk/", ->
    nbLinks = @evaluate ->
        return __utils__.findAll('#promo2_carousel_items_items li').length
    @echo "#{nbLinks} items founds"
    # hide navigation arrows
    @hide ".nav_left"
    @hide ".nav_right"
    @mouse.move "#promo2_carousel"

casper.waitUntilVisible ".autoplay.nav_pause", ->
    @echo "Moving over pause button"
    @mouse.move ".autoplay.nav_pause"
    @click ".autoplay.nav_pause"
    @echo "Clicked on pause button"
    @waitUntilVisible ".autoplay.nav_play", ->
        @echo "Carousel has been paused"
        # hide play button
        @hide ".autoplay"

# Capture carrousel area
next = ->
    image = "bbcshot#{currentLink}.png"
    images.push image
    @echo "Processing image #{currentLink}"
    @captureSelector image, '.carousel_viewport'
    if currentLink < nbLinks
        @click ".carousel_itemList_li[rel='#{currentLink}']"
        @wait 1000, ->
            @then next
            currentLink++
    else
        @then buildPage

# Building resulting page and image
buildPage = ->
    @echo "Build result page"
    fs = require "fs"
    @viewport 624, 400
    pageHtml = "<html><body style='background:black;margin:0;padding:0'>"
    images.forEach (image) ->
        pageHtml += "<img src='file://#{fs.workingDirectory}/#{image}'><br>"
    pageHtml += "</body></html>"
    fs.write "result.html", pageHtml, 'w'
    @thenOpen "file://#{fs.workingDirectory}/result.html", ->
        @echo "Resulting image saved to result.png"
        @capture "result.png"

casper.then next

casper.run()
