const noop = () => {};
const { JSDOM } = require("jsdom");
const fs = require("fs");

const template = fs.readFileSync("templates/corporate/billing.html", "utf-8");
const dom = new JSDOM(template, { pretendToBeVisual: true });
const document = dom.window.document;

var jquery_init;
global.$ = (f) => {jquery_init = f;};
set_global('helpers', {
    set_tab: noop,
});
set_global('StripeCheckout', {
    configure: noop,
});

zrequire('billing', "js/billing/billing");
set_global('$', global.make_zjquery());

run_test("initialize", () => {
    var token_func;
    helpers.set_tab = (page_name) => {
        assert.equal(page_name, "billing");
    };

    helpers.create_ajax_request = (url, form_name, stripe_token) => {
        assert.equal(url, "/json/billing/sources/change");
        assert.equal(form_name, "cardchange");
        assert.equal(stripe_token, "stripe_token");
    };

    const open_func = (config_opts) => {
        assert.equal(config_opts.name, "Zulip");
        assert.equal(config_opts.zipCode, true);
        assert.equal(config_opts.billingAddress, true);
        assert.equal(config_opts.panelLabel, "Update card");
        assert.equal(config_opts.label, "Update card");
        assert.equal(config_opts.allowRememberMe, false);
        assert.equal(config_opts.email, "{{stripe_email}}");

        token_func("stripe_token");
    };

    StripeCheckout.configure = (config_opts) => {
        assert.equal(config_opts.image, '/static/images/logo/zulip-icon-128x128.png');
        assert.equal(config_opts.locale, 'auto');
        assert.equal(config_opts.key, '{{publishable_key}}');
        token_func = config_opts.token;

        return {
            open: open_func,
        };
    };

    $("#payment-method").data = (key) => {
        return document.querySelector("#payment-method").getAttribute("data-" + key);
    };

    jquery_init();

    const e = {
        preventDefault: noop,
    };
    const click_handler = $('#update-card-button').get_on_handler('click');
    click_handler(e);
});

run_test("billing_template", () => {
    // Elements necessary for create_ajax_request
    assert(document.querySelector("#cardchange-error"));
    assert(document.querySelector("#cardchange-loading"));
    assert(document.querySelector("#cardchange_loading_indicator"));
    assert(document.querySelector("#cardchange-success"));

    assert(document.querySelector("input[name=csrfmiddlewaretoken]"));
});
