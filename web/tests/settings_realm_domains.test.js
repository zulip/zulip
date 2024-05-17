"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

const channel = mock_esm("../src/channel");
mock_esm("../src/ui_report", {
    success(msg, elem) {
        elem.val(msg);
    },

    error(msg, _xhr, elem) {
        elem.val(msg);
    },
});

const settings_realm_domains = zrequire("settings_realm_domains");

function test_realms_domain_modal(override, add_realm_domain) {
    const $info = $(".realm_domains_info");

    $("#add-realm-domain-widget").set_find_results(
        ".new-realm-domain",
        $.create("new-realm-domain-stub"),
    );

    $("#add-realm-domain-widget").set_find_results(
        "input.new-realm-domain-allow-subdomains",
        $("<new-realm-domain-allow-subdomains-stub>"),
    );
    $("<new-realm-domain-allow-subdomains-stub>")[0] = {};

    let posted;
    let success_callback;
    let error_callback;
    override(channel, "post", (req) => {
        posted = true;
        assert.equal(req.url, "/json/realm/domains");
        success_callback = req.success;
        error_callback = req.error;
    });

    add_realm_domain();

    assert.ok(posted);

    success_callback();
    assert.equal($info.val(), "translated HTML: Added successfully!");

    error_callback({});
    assert.equal($info.val(), "translated HTML: Failed");
}

function test_change_allow_subdomains(change_allow_subdomains) {
    const ev = {
        stopPropagation: noop,
    };

    const $info = $(".realm_domains_info");
    $info.fadeOut = noop;
    const domain = "example.com";
    let allow = true;

    let success_callback;
    let error_callback;
    channel.patch = (req) => {
        assert.equal(req.url, "/json/realm/domains/example.com");
        assert.equal(req.data.allow_subdomains, JSON.stringify(allow));
        success_callback = req.success;
        error_callback = req.error;
    };

    const $domain_obj = $.create("domain object");
    $domain_obj.text(domain);

    const $elem_obj = $.create("<elem html>");
    const elem_obj = {to_$: () => $elem_obj};
    const $parents_obj = $.create("parents object");

    $elem_obj.set_parents_result("tr", $parents_obj);
    $parents_obj.set_find_results(".domain", $domain_obj);
    elem_obj.checked = allow;

    change_allow_subdomains.call(elem_obj, ev);

    success_callback();
    assert.equal(
        $info.val(),
        "translated HTML: Update successful: Subdomains allowed for example.com",
    );

    error_callback({});
    assert.equal($info.val(), "translated HTML: Failed");

    allow = false;
    elem_obj.checked = allow;
    change_allow_subdomains.call(elem_obj, ev);
    success_callback();
    assert.equal(
        $info.val(),
        "translated HTML: Update successful: Subdomains no longer allowed for example.com",
    );
}

run_test("test_realm_domains_table", ({override}) => {
    settings_realm_domains.setup_realm_domains_modal_handlers();
    test_realms_domain_modal(override, () => $("#submit-add-realm-domain").trigger("click"));
    test_change_allow_subdomains(
        $("#realm_domains_table").get_on_handler("change", "input.allow-subdomains"),
    );
});
