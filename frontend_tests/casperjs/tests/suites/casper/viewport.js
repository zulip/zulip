/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.viewport()');

casper.start();

casper.viewport(1337, 999);

casper.test.assertEquals(casper.page.viewportSize.width, 1337, 'Casper.viewport() can change the width of page viewport');
casper.test.assertEquals(casper.page.viewportSize.height, 999, 'Casper.viewport() can change the height of page viewport');
casper.test.assertRaises(casper.viewport, ['a', 'b'], 'Casper.viewport() validates viewport size data');

casper.test.done(3);
