"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const gear_menu_util = zrequire("gear_menu_util");
const {set_realm} = zrequire("state_data");

const realm = {};
set_realm(realm);

run_test("version_display_string", ({override}) => {
    let expected_version_display_string;

    // An official release
    override(realm, "zulip_version", "5.6");
    override(realm, "zulip_merge_base", "5.6");
    expected_version_display_string = "translated: Zulip Server 5.6";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // An official beta
    override(realm, "zulip_version", "6.0-beta1");
    override(realm, "zulip_merge_base", "6.0-beta1");
    expected_version_display_string = "translated: Zulip Server 6.0-beta1";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // An official release candidate
    override(realm, "zulip_version", "6.0-rc1");
    override(realm, "zulip_merge_base", "6.0-rc1");
    expected_version_display_string = "translated: Zulip Server 6.0-rc1";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // The Zulip development environment
    override(realm, "zulip_version", "6.0-dev+git");
    override(realm, "zulip_merge_base", "6.0-dev+git");
    expected_version_display_string = "translated: Zulip Server dev environment";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // A commit on Zulip's main branch.
    override(realm, "zulip_version", "6.0-dev-1976-g4bb381fc80");
    override(realm, "zulip_merge_base", "6.0-dev-1976-g4bb381fc80");
    expected_version_display_string = "translated: Zulip Server 6.0-dev";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // A fork with 18 commits beyond Zulip's main branch.
    override(realm, "zulip_version", "6.0-dev-1994-g93730766b0");
    override(realm, "zulip_merge_base", "6.0-dev-1976-g4bb381fc80");
    expected_version_display_string = "translated: Zulip Server 6.0-dev (modified)";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // A commit from the Zulip 5.x branch
    override(realm, "zulip_version", "5.6+git-4-g385a408be5");
    override(realm, "zulip_merge_base", "5.6+git-4-g385a408be5");
    expected_version_display_string = "translated: Zulip Server 5.6 (patched)";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // A fork with 3 commits beyond the Zulip 5.x branch.
    override(realm, "zulip_version", "5.6+git-4-g385a408be5");
    override(realm, "zulip_merge_base", "5.6+git-7-abcda4235c2");
    expected_version_display_string = "translated: Zulip Server 5.6 (modified)";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);

    // A fork of a Zulip release commit, not on 5.x branch.
    override(realm, "zulip_version", "5.3-1-g7ed896c0db");
    override(realm, "zulip_merge_base", "5.3");
    expected_version_display_string = "translated: Zulip Server 5.3 (modified)";
    assert.equal(gear_menu_util.version_display_string(), expected_version_display_string);
});
