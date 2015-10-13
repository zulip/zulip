/*global casper*/
/*jshint strict:false*/
// events

casper.test.comment("events");

casper.plopped = false;

casper.on("plop", function() {
    this.plopped = true;
});

casper.test.assert(Object.keys(casper._events).some(function(i) {
    return i === "plop";
}), "on() has set an event handler");

casper.emit("plop");

casper.test.assert(casper.plopped, "emit() emits an event");

// filters

casper.test.comment("filters");

casper.foo = 0;
casper.setFilter("test", function(a) {
    this.foo = 42;
    return a + 1;
});

casper.test.assert(Object.keys(casper._filters).some(function(i) {
    return i === "test";
}), "setFilter() has set a filter");

casper.test.assertEquals(casper.filter("test", 1), 2, "filter() filters a value");
casper.test.assertEquals(casper.foo, 42, "filter() applies the correct context");

delete casper.foo;

casper.test.done(5);
