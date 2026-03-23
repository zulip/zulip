"use strict";

const $ = require("./zjquery.cjs");

let users_matching_view = [];
exports.buddy_list_add_user_matching_view = (user_id, $stub) => {
    if ($stub.attr) {
        $stub.attr("data-user-id", user_id);
    }
    users_matching_view.push(user_id);
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#buddy_list_wrapper").set_find_results(sel, $stub);
};

let other_users = [];
exports.buddy_list_add_other_user = (user_id, $stub) => {
    if ($stub.attr) {
        $stub.attr("data-user-id", user_id);
    }
    other_users.push(user_id);
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#buddy_list_wrapper").set_find_results(sel, $stub);
};

exports.override_user_matches_narrow_using_loaded_data = (user_id) =>
    users_matching_view.includes(user_id);

exports.clear_buddy_list = (buddy_list) => {
    buddy_list.populate({
        all_user_ids: [],
    });
    users_matching_view = [];
    other_users = [];
};

exports.stub_buddy_list_elements = () => {
    // Set to an empty list since we're not testing CSS.
    $.reset_selector("#buddy-list-users-matching-view .empty-list-message");
    $.set_results("#buddy-list-users-matching-view .empty-list-message", []);
    $.reset_selector("#buddy-list-other-users .empty-list-message");
    $.set_results("#buddy-list-other-users .empty-list-message", []);
    $.reset_selector("#buddy-list-other-users-container .view-all-users-link");
    $.set_results("#buddy-list-other-users-container .view-all-users-link", []);

    // Simulate no avatar images for clear_avatar_preload_backgrounds.
    $.reset_selector("#user-list .avatar-preload-background img");
    $.set_results("#user-list .avatar-preload-background img", []);
};
