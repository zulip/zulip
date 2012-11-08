/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/global.html', function() {
    this.test.comment('Casper.getGlobal()');
    this.test.assertEquals(this.getGlobal('myGlobal'), 'awesome string', 'Casper.getGlobal() can retrieve a remote global variable');
    this.test.assertRaises(this.getGlobal, ['myUnencodableGlobal'], 'Casper.getGlobal() does not fail trying to encode an unencodable global');
});

casper.run(function() {
    this.test.done();
});
