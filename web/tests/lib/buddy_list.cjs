"use strict";

const {noop} = require("./test.cjs");
const $ = require("./zjquery.cjs");

let users_matching_view = [];
exports.buddy_list_add_user_matching_view = (user_id, $stub) => {
    if ($stub.attr) {
        $stub.attr("data-user-id", user_id);
    }
    $stub.length = 1;
    users_matching_view.push(user_id);
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#buddy_list_wrapper").set_find_results(sel, $stub);
};

let other_users = [];
exports.buddy_list_add_other_user = (user_id, $stub) => {
    if ($stub.attr) {
        $stub.attr("data-user-id", user_id);
    }
    $stub.length = 1;
    other_users.push(user_id);
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#buddy_list_wrapper").set_find_results(sel, $stub);
};

exports.override_user_matches_narrow = (user_id) => users_matching_view.includes(user_id);

exports.clear_buddy_list = (buddy_list) => {
    buddy_list.populate({
        all_user_ids: [],
    });
    users_matching_view = [];
    other_users = [];
};

exports.stub_buddy_list_elements = () => {
    // Set to an empty list since we're not testing CSS.
    $("#buddy-list-users-matching-view").children = () => [];
    $("#buddy-list-users-matching-view .empty-list-message").length = 0;
    $("#buddy-list-other-users .empty-list-message").length = 0;
    $("#buddy-list-other-users-container .view-all-users-link").length = 0;
    $("#buddy-list-users-matching-view-container .view-all-subscribers-link").empty = noop;
    $("#buddy-list-other-users-container .view-all-users-link").empty = noop;
    $(`#buddy-list-users-matching-view .empty-list-message`).remove = noop;
    $(`#buddy-list-other-users .empty-list-message`).remove = noop;
    $(`#buddy-list-participants .empty-list-message`).remove = noop;
};
