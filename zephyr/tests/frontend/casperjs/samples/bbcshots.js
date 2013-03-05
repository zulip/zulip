/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * Create a mosaic image from all headline photos on BBC homepage
 */
var casper = require("casper").create();
var nbLinks = 0;
var currentLink = 1;
var images = [];
var buildPage, next;

// helper to hide some element from remote DOM
casper.hide = function(selector) {
    this.evaluate(function(selector) {
        document.querySelector(selector).style.display = "none";
    }, selector);
};

casper.start("http://www.bbc.co.uk/", function() {
    nbLinks = this.evaluate(function() {
        return __utils__.findAll('#promo2_carousel_items_items li').length;
    });
    this.echo(nbLinks + " items founds");
    // hide navigation arrows
    this.hide(".nav_left");
    this.hide(".nav_right");
    this.mouse.move("#promo2_carousel");
});

casper.waitUntilVisible(".autoplay.nav_pause", function() {
    this.echo("Moving over pause button");
    this.mouse.move(".autoplay.nav_pause");
    this.click(".autoplay.nav_pause");
    this.echo("Clicked on pause button");
    this.waitUntilVisible(".autoplay.nav_play", function() {
        this.echo("Carousel has been paused");
        // hide play button
        this.hide(".autoplay");
    });
});

// Capture carrousel area
next = function() {
    var image;
    image = "bbcshot" + currentLink + ".png";
    images.push(image);
    this.echo("Processing image " + currentLink);
    this.captureSelector(image, '.carousel_viewport');
    if (currentLink < nbLinks) {
        this.click(".carousel_itemList_li[rel='" + currentLink + "']");
        this.wait(1000, function() {
            this.then(next);
            currentLink++;
        });
    } else {
        this.then(buildPage);
    }
};

// Building resulting page and image
buildPage = function() {
    var fs, pageHtml;
    this.echo("Build result page");
    fs = require("fs");
    this.viewport(624, 400);
    pageHtml = "<html><body style='background:black;margin:0;padding:0'>";
    images.forEach(function(image) {
        pageHtml += "<img src='file://" + fs.workingDirectory + "/" + image + "'><br>";
    });
    pageHtml += "</body></html>";
    fs.write("result.html", pageHtml, 'w');
    this.thenOpen("file://" + fs.workingDirectory + "/result.html", function() {
        this.echo("Resulting image saved to result.png");
        this.capture("result.png");
    });
};

casper.then(next);

casper.run();
