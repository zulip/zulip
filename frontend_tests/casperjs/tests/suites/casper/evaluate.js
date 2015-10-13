/*global casper*/
/*jshint strict:false maxparams:99*/
casper.test.comment('Casper.evaluate()');

casper.start();

var context = {
    "_boolean_true":  true,
    "_boolean_false": false,
    "_int_number":    42,
    "_float_number":  1337.42,
    "_string":        "plop! \"Ÿ£$\" 'no'",
    "_array":         [1, 2, 3],
    "_object":        {a: 1, b: 2},
    "_function":      function(){console.log('ok');}
};

var result = casper.evaluate(function(_boolean_true,
                                      _boolean_false,
                                      _int_number,
                                      _float_number,
                                      _string,
                                      _array,
                                      _object,
                                      _function) {
    return [].map.call(arguments, function(arg) {
        return typeof(arg);
    });
}, context);

casper.test.assertEquals(result.toString(),
                         ['boolean', 'boolean', 'number', 'number', 'string', 'object', 'object', 'function'].toString(),
                         'Casper.evaluate() handles passed argument context correcly');

// no context
casper.test.assertEquals(casper.evaluate(function() {
    return 42;
}), 42, 'Casper.evaluate() handles evaluation with no context passed');

// object context (previous casperjs versions compatibility mode)
casper.test.assertEquals(casper.evaluate(function(a) {
    return [a];
}, {a: "foo"}), ["foo"], 'Casper.evaluate() accepts an object as arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b) {
    return [a, b];
}, {a: "foo", b: "bar"}), ["foo", "bar"], 'Casper.evaluate() accepts an object as arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b, c) {
    return [a, b, c];
}, {a: "foo", b: "bar", c: "baz"}), ["foo", "bar", "baz"], 'Casper.evaluate() accepts an object as arguments context');

// array context
casper.test.assertEquals(casper.evaluate(function(a) {
    return [a];
}, ["foo"]), ["foo"], 'Casper.evaluate() accepts an array as arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b) {
    return [a, b];
}, ["foo", "bar"]), ["foo", "bar"], 'Casper.evaluate() accepts an array as arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b, c) {
    return [a, b, c];
}, ["foo", "bar", "baz"]), ["foo", "bar", "baz"], 'Casper.evaluate() accepts an array as arguments context');

// natural arguments context (phantomjs equivalent)
casper.test.assertEquals(casper.evaluate(function(a) {
    return [a];
}, "foo"), ["foo"], 'Casper.evaluate() accepts natural arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b) {
    return [a, b];
}, "foo", "bar"), ["foo", "bar"], 'Casper.evaluate() accepts natural arguments context');
casper.test.assertEquals(casper.evaluate(function(a, b, c) {
    return [a, b, c];
}, "foo", "bar", "baz"), ["foo", "bar", "baz"], 'Casper.evaluate() accepts natural arguments context');

casper.start().thenEvaluate(function(a, b) {
    window.a = a
    window.b = b;
}, "foo", "bar");

casper.then(function() {
    this.test.comment('Casper.thenEvaluate()');
    this.test.assertEquals(this.getGlobal('a'), "foo", "Casper.thenEvaluate() sets args");
    this.test.assertEquals(this.getGlobal('b'), "bar",
        "Casper.thenEvaluate() sets args the same way evaluate() does");
});

casper.run(function() {
    this.test.done(13);
});
