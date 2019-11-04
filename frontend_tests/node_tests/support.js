const fs = require("fs");
const { JSDOM } = require("jsdom");
const template = fs.readFileSync("templates/analytics/realm_details.html", "utf-8");
const dom = new JSDOM(template, { pretendToBeVisual: true });
const document = dom.window.document;

let jquery_init;
global.$ = (f) => {jquery_init = f;};
zrequire('support', "js/analytics/support");
set_global('$', global.make_zjquery());

run_test('scrub_realm', () => {
    jquery_init();
    const click_handler = $('body').get_on_handler('click', '.scrub-realm-button');
    assert.equal(typeof click_handler, 'function');

    assert.equal(document.querySelectorAll(".scrub-realm-button").length, 1);
});
