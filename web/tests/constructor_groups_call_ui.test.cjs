"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// Mock dependencies exactly like compose_video.test.cjs
const channel = mock_esm("../src/channel");
const compose_ui = mock_esm("../src/compose_ui");
const compose_banner = mock_esm("../src/compose_banner");
set_global("document", {
    querySelector() {},
});

const compose_call_ui = zrequire("compose_call_ui");
const {set_current_user, set_realm} = zrequire("state_data");

// Global mock for compose_banner functions
compose_banner.clear_constructor_groups_errors = () => {};
compose_banner.show_constructor_groups_error = () => {};

// Setup realm and user like compose_video.test.cjs
const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);

const realm_available_video_chat_providers = {
    constructor_groups: {
        id: 6,
        name: "Constructor Groups",
    },
};

run_test("constructor_groups_video_call_generation", ({override}) => {
    // Setup realm like other video providers
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.constructor_groups.id);
    override(realm, "realm_available_video_chat_providers", realm_available_video_chat_providers);
    
    const $textarea = $.create("textarea#compose-textarea");
    $textarea.set_parents_result(".message_edit_form", []);
    
    // Mock the clear_constructor_groups_errors function
    override(compose_banner, "clear_constructor_groups_errors", () => {});
    
    let channel_post_called = false;
    let api_url = "";
    let api_data = {};
    
    // Mock channel.post like in compose_video tests
    override(channel, "post", (opts) => {
        channel_post_called = true;
        api_url = opts.url;
        api_data = opts.data;
        
        // Simulate successful API response
        opts.success({
            url: "https://constructor.app/groups/room/room-123",
            result: "success",
            msg: "",
        });
        
        return {abort: () => {}};
    });
    
    let syntax_inserted = "";
    let insert_called = false;
    
    // Mock compose_ui.insert_syntax_and_focus like other tests
    override(compose_ui, "insert_syntax_and_focus", (syntax) => {
        syntax_inserted = syntax;
        insert_called = true;
    });
    
    // Call the function under test
    compose_call_ui.generate_and_insert_audio_or_video_call_link($textarea, false);
    
    // Verify API call was made correctly
    assert(channel_post_called);
    assert.equal(api_url, "/json/calls/constructorgroups/create");
    assert.equal(api_data.is_video_call, true);
    
    // Verify UI insertion was called
    assert(insert_called);
    assert.match(syntax_inserted, /https:\/\/constructor\.app\/groups\/room\/room-123/);
});

run_test("constructor_groups_audio_call_generation", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.constructor_groups.id);
    override(realm, "realm_available_video_chat_providers", realm_available_video_chat_providers);
    
    const $textarea = $.create("textarea#compose-textarea");
    $textarea.set_parents_result(".message_edit_form", []);
    
    // Mock the clear_constructor_groups_errors function
    override(compose_banner, "clear_constructor_groups_errors", () => {});
    
    let api_data = {};
    override(channel, "post", (opts) => {
        api_data = opts.data;
        opts.success({
            url: "https://constructor.app/groups/room/room-456",
            result: "success",
            msg: "",
        });
        return {abort: () => {}};
    });
    
    let insert_called = false;
    override(compose_ui, "insert_syntax_and_focus", () => {
        insert_called = true;
    });
    
    // Test audio call (is_audio_call = true)
    compose_call_ui.generate_and_insert_audio_or_video_call_link($textarea, true);
    
    // Verify audio call parameter
    assert.equal(api_data.is_video_call, false);
    assert(insert_called);
});

run_test("constructor_groups_error_handling", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.constructor_groups.id);
    override(realm, "realm_available_video_chat_providers", realm_available_video_chat_providers);
    
    const $textarea = $.create("textarea#compose-textarea");
    $textarea.set_parents_result(".message_edit_form", []);
    
    let error_shown = false;
    let error_message = "";
    
    // Override show_constructor_groups_error for this test
    override(compose_banner, "show_constructor_groups_error", (message) => {
        error_shown = true;
        error_message = message;
    });

    
    // Mock API error
    override(channel, "post", (opts) => {
        opts.error({
            responseJSON: {
                code: "CONSTRUCTOR_GROUPS_NOT_CONFIGURED",
                msg: "Constructor Groups is not configured.",
            },
        }, "error");
        return {abort: () => {}};
    });
    
    compose_call_ui.generate_and_insert_audio_or_video_call_link($textarea, false);
    
    // Verify error handling
    assert(error_shown);
    assert(error_message.toString().includes("Constructor Groups is not configured"));
});

run_test("constructor_groups_concurrent_clicks_abort_previous", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.constructor_groups.id);
    override(realm, "realm_available_video_chat_providers", realm_available_video_chat_providers);
    
    const $textarea = $.create("textarea#compose-textarea");
    $textarea.set_parents_result(".message_edit_form", []);
    
    override(compose_banner, "clear_constructor_groups_errors", () => {});
    
    let first_request_aborted = false;
    let second_request_made = false;
    let api_call_count = 0;
    
    // Mock channel.post to track XHR objects and abort calls
    override(channel, "post", (opts) => {
        api_call_count++;
        
        if (api_call_count === 1) {
            // First request - should be aborted when second request starts
            const mock_xhr = {
                abort: () => {
                    first_request_aborted = true;
                }
            };
            return mock_xhr;
        } else {
            // Second request - should complete successfully
            second_request_made = true;
            opts.success({
                url: "https://constructor.app/groups/room/room-789",
                result: "success",
                msg: "",
            });
            return {abort: () => {}};
        }
    });
    
    let insert_called = false;
    override(compose_ui, "insert_syntax_and_focus", () => {
        insert_called = true;
    });
    
    // First click - starts first request
    compose_call_ui.generate_and_insert_audio_or_video_call_link($textarea, false);
    
    // Second click immediately after - should abort first request and start new one
    compose_call_ui.generate_and_insert_audio_or_video_call_link($textarea, false);
    
    // Verify behavior
    assert(first_request_aborted, "First request should be aborted");
    assert(second_request_made, "Second request should be made");
    assert.equal(api_call_count, 2, "Should make exactly 2 API calls");
    assert(insert_called, "Should insert syntax after second request completes");
});