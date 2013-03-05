/*global casper*/
/*jshint strict:false maxstatements:99*/
var cli = require('cli'), t = casper.test;

t.comment('parse(), get(), has()');

(function(parsed) {
    // clean
    t.assertEquals(parsed.args, [], 'parse() returns expected positional args array');
    t.assertEquals(parsed.options, {}, 'parse() returns expected options object');
    t.assertEquals(parsed.get(0), undefined, 'parse() does not return inexistant positional arg');
    t.assertEquals(parsed.get('blah'), undefined, 'parse() does not return inexistant option');
    t.assert(!parsed.has(0), 'has() checks if an arg is set');
    t.assert(!parsed.has('blah'), 'has() checks if an option is set');
    // raw
    t.assertEquals(parsed.raw.args, [], 'parse() returns expected positional args array');
    t.assertEquals(parsed.raw.options, {}, 'parse() returns expected options object');
    t.assertEquals(parsed.raw.get(0), undefined, 'parse() does not return inexistant positional arg');
    t.assertEquals(parsed.raw.get('blah'), undefined, 'parse() does not return inexistant option');
    t.assert(!parsed.raw.has(0), 'has() checks if a raw arg is set');
    t.assert(!parsed.raw.has('blah'), 'has() checks if a raw option is set');
})(cli.parse([]));

(function(parsed) {
    // clean
    t.assertEquals(parsed.args, ['foo', 'bar'], 'parse() returns expected positional args array');
    t.assertEquals(parsed.options, {}, 'parse() returns expected options object');
    t.assertEquals(parsed.get(0), 'foo', 'parse() retrieve first positional arg');
    t.assertEquals(parsed.get(1), 'bar', 'parse() retrieve second positional arg');
    t.assert(parsed.has(0), 'has() checks if an arg is set');
    t.assert(parsed.has(1), 'has() checks if an arg is set');
    t.assert(!parsed.has(2), 'has() checks if an arg is not set');
    // raw
    t.assertEquals(parsed.raw.args, ['foo', 'bar'], 'parse() returns expected positional raw args array');
    t.assertEquals(parsed.raw.options, {}, 'parse() returns expected raw options object');
    t.assertEquals(parsed.raw.get(0), 'foo', 'parse() retrieve first positional raw arg');
    t.assertEquals(parsed.raw.get(1), 'bar', 'parse() retrieve second positional raw arg');
    t.assert(parsed.raw.has(0), 'has() checks if a arw arg is set');
    t.assert(parsed.raw.has(1), 'has() checks if a arw arg is set');
    t.assert(!parsed.raw.has(2), 'has() checks if a arw arg is not set');
})(cli.parse(['foo', 'bar']));

(function(parsed) {
    // clean
    t.assertEquals(parsed.args, [], 'parse() returns expected positional args array');
    t.assertEquals(parsed.options, {foo: 'bar', baz: true}, 'parse() returns expected options object');
    t.assertEquals(parsed.get('foo'), 'bar', 'parse() retrieve an option value');
    t.assert(parsed.get('baz'), 'parse() retrieve boolean option flag');
    t.assert(parsed.has("foo"), 'has() checks if an option is set');
    t.assert(parsed.has("baz"), 'has() checks if an option is set');
    // raw
    t.assertEquals(parsed.raw.args, [], 'parse() returns expected positional raw args array');
    t.assertEquals(parsed.raw.options, {foo: 'bar', baz: true}, 'parse() returns expected options raw object');
    t.assertEquals(parsed.raw.get('foo'), 'bar', 'parse() retrieve an option raw value');
    t.assert(parsed.raw.get('baz'), 'parse() retrieve boolean raw option flag');
    t.assert(parsed.raw.has("foo"), 'has() checks if a raw option is set');
    t.assert(parsed.raw.has("baz"), 'has() checks if a raw option is set');
})(cli.parse(['--foo=bar', '--baz']));

(function(parsed) {
    // clean
    t.assertEquals(parsed.args, [], 'parse() returns expected positional args array');
    t.assertEquals(parsed.options, { '&é"à': "42===42" }, 'parse() returns expected options object');
    t.assertEquals(parsed.get('&é"à'), "42===42", 'parse() handles options with exotic names');
    t.assert(parsed.has('&é"à'), 'has() checks if an option is set');
    // raw
    t.assertEquals(parsed.raw.args, [], 'parse() returns expected positional raw args array');
    t.assertEquals(parsed.raw.options, { '&é"à': "42===42" }, 'parse() returns expected options raw object');
    t.assertEquals(parsed.raw.get('&é"à'), "42===42", 'parse() handles raw options with exotic names');
    t.assert(parsed.raw.has('&é"à'), 'has() checks if a raw option is set');
})(cli.parse(['--&é"à=42===42']));

(function(parsed) {
    // clean
    t.assertEquals(parsed.args, ['foo & bar', 'baz & boz'], 'parse() returns expected positional args array');
    t.assertEquals(parsed.options, { universe: 42, lap: 13.37, chucknorris: true, oops: false }, 'parse() returns expected options object');
    t.assertEquals(parsed.get('universe'), 42, 'parse() can cast a numeric option value');
    t.assertEquals(parsed.get('lap'), 13.37, 'parse() can cast a float option value');
    t.assertType(parsed.get('lap'), "number", 'parse() can cast a boolean value');
    t.assert(parsed.get('chucknorris'), 'parse() can get a flag value by its option name');
    t.assertType(parsed.get('oops'), "boolean", 'parse() can cast a boolean value');
    t.assertEquals(parsed.get('oops'), false, 'parse() can cast a boolean value');
    t.assert(parsed.has(0), 'has() checks if an arg is set');
    t.assert(parsed.has(1), 'has() checks if an arg is set');
    t.assert(parsed.has("universe"), 'has() checks if an option is set');
    t.assert(parsed.has("lap"), 'has() checks if an option is set');
    t.assert(parsed.has("chucknorris"), 'has() checks if an option is set');
    t.assert(parsed.has("oops"), 'has() checks if an option is set');

    t.comment('drop()');

    parsed.drop(0);
    t.assertEquals(parsed.get(0), 'baz & boz', 'drop() dropped arg');
    parsed.drop("universe");
    t.assert(!parsed.has("universe"), 'drop() dropped option');
    t.assertEquals(parsed.args, ["baz & boz"], 'drop() did not affect other args');
    t.assertEquals(parsed.options, {
        lap: 13.37,
        chucknorris: true,
        oops: false
    }, 'drop() did not affect other options');

    // raw
    t.assertEquals(parsed.raw.args, ['foo & bar', 'baz & boz'], 'parse() returns expected positional raw args array');
    t.assertEquals(parsed.raw.options, { universe: "42", lap: "13.37", chucknorris: true, oops: "false" }, 'parse() returns expected options raw object');
    t.assertEquals(parsed.raw.get('universe'), "42", 'parse() does not a raw numeric option value');
    t.assertEquals(parsed.raw.get('lap'), "13.37", 'parse() does not cast a raw float option value');
    t.assertType(parsed.raw.get('lap'), "string", 'parse() does not cast a numeric value');
    t.assert(parsed.raw.get('chucknorris'), 'parse() can get a flag value by its option name');
    t.assertType(parsed.raw.get('oops'), "string", 'parse() can cast a boolean value');
    t.assertEquals(parsed.raw.get('oops'), "false", 'parse() can cast a boolean value');

    t.comment('drop() for raw');

    parsed.raw.drop(0);
    t.assertEquals(parsed.raw.get(0), 'baz & boz', 'drop() dropped raw arg');
    parsed.raw.drop("universe");
    t.assert(!parsed.raw.has("universe"), 'drop() dropped raw option');
    t.assertEquals(parsed.raw.args, ["baz & boz"], 'drop() did not affect other raw args');
    t.assertEquals(parsed.raw.options, {
        lap: "13.37",
        chucknorris: true,
        oops: "false"
    }, 'drop() did not affect other raw options');
})(cli.parse(['foo & bar', 'baz & boz', '--universe=42', '--lap=13.37', '--chucknorris', '--oops=false']));

t.done(76);
