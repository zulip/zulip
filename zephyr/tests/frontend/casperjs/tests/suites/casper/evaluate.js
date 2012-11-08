/*global casper*/
/*jshint strict:false*/
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

casper.test.done();
