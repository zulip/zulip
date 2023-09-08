"use strict";

const compose_banner = require("../../src/compose_banner");

const $ = require("./zjquery");

exports.mock_banners = () => {
    // zjquery doesn't support `remove`, which is used when clearing the compose box.
    // TODO: improve how we test this so that we don't have to mock things like this.
    for (const classname of Object.values(compose_banner.CLASSNAMES)) {
        $(
            `#compose_banners .${classname
                .split(" ")
                .map((classname) => CSS.escape(classname))
                .join(".")}`,
        ).remove = () => {};
    }
    $("#compose_banners .warning").remove = () => {};
    $("#compose_banners .error").remove = () => {};
    $("#compose_banners .upload_banner").remove = () => {};

    const $stub = $.create("stub_to_remove");
    const $cb = $("#compose_banners");

    $stub.remove = () => {};
    $stub.length = 0;

    $cb.closest = () => [];
    $cb.set_find_results(".no_post_permissions", $stub);
    $cb.set_find_results(".message_too_long", $stub);
    $cb.set_find_results(".wildcards_not_allowed", $stub);
    $cb.set_find_results(".wildcard_warning", $stub);
    $cb.set_find_results(".topic_missing", $stub);
    $cb.set_find_results(".missing_stream", $stub);
    $cb.set_find_results(".zephyr_not_running", $stub);
    $cb.set_find_results(".deactivated_user", $stub);
    $cb.set_find_results(".missing_private_message_recipient", $stub);
    $cb.set_find_results(".subscription_error", $stub);
    $cb.set_find_results(".generic_compose_error", $stub);
};
