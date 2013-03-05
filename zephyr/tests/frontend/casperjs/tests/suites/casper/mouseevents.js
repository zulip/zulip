/*global casper*/
/*jshint strict:false maxstatements:99*/
casper.start('tests/site/mouse-events.html');

casper.then(function() {
    this.test.comment('CasperUtils.mouseEvent()');
    this.test.assert(this.mouseEvent('mousedown', '#test1'), 'CasperUtils.mouseEvent() can dispatch a mousedown event');
    this.test.assert(this.mouseEvent('mousedown', '#test2'), 'CasperUtils.mouseEvent() can dispatch a mousedown event handled by unobstrusive js');
    this.test.assert(this.mouseEvent('mouseup', '#test3'), 'CasperUtils.mouseEvent() can dispatch a mouseup event');
    this.test.assert(this.mouseEvent('mouseup', '#test4'), 'CasperUtils.mouseEvent() can dispatch a mouseup event handled by unobstrusive js');
    this.test.assert(this.mouseEvent('mouseover', '#test5'), 'CasperUtils.mouseEvent() can dispatch a mouseover event');
    this.test.assert(this.mouseEvent('mouseover', '#test6'), 'CasperUtils.mouseEvent() can dispatch a mouseover event handled by unobstrusive js');
    this.test.assert(this.mouseEvent('mouseout', '#test7'), 'CasperUtils.mouseEvent() can dispatch a mouseout event');
    this.test.assert(this.mouseEvent('mouseout', '#test8'), 'CasperUtils.mouseEvent() can dispatch a mouseout event handled by unobstrusive js');

    var results = this.getGlobal('results');
    this.test.assert(results.test1, 'CasperUtils.mouseEvent() triggered mousedown');
    this.test.assert(results.test2, 'CasperUtils.mouseEvent() triggered mousedown via unobstrusive js');
    this.test.assert(results.test3, 'CasperUtils.mouseEvent() triggered mouseup');
    this.test.assert(results.test4, 'CasperUtils.mouseEvent() triggered mouseup via unobstrusive js');
    this.test.assert(results.test5, 'CasperUtils.mouseEvent() triggered mouseover');
    this.test.assert(results.test6, 'CasperUtils.mouseEvent() triggered mouseover via unobstrusive js');
    this.test.assert(results.test7, 'CasperUtils.mouseEvent() triggered mouseout');
    this.test.assert(results.test8, 'CasperUtils.mouseEvent() triggered mouseout via unobstrusive js');
});

casper.run(function() {
    this.test.done(16);
});
