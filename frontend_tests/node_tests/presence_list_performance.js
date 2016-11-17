// TODO: de-dup with activity.js
global.stub_out_jquery();

set_global('document', {
    hasFocus: function () {
        return true;
    }
});
set_global('feature_flags', {});
set_global('page_params', {});

add_dependencies({
   Handlebars: 'handlebars',
   templates: 'js/templates',
   util: 'js/util.js',
   compose_fade: 'js/compose_fade.js',
   people: 'js/people.js',
   unread: 'js/unread.js',
   activity: 'js/activity.js'
});

var compose_fade = require('js/compose_fade.js');
compose_fade.update_faded_users = function () {
   return;
};

var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);
$.fn.expectOne = function () {
    assert(this.length === 1);
    return this;
};

global.compile_template('user_presence_row');
global.compile_template('user_presence_rows');

var people = require("js/people.js");
var activity = require('js/activity.js');

// TODO: de-dup with activity.js
var alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith'
};
var fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone"
};
var jill = {
    email: 'jill@zulip.com',
    user_id: 3,
    full_name: 'Jill Hill'
};
var mark = {
    email: 'mark@zulip.com',
    user_id: 4,
    full_name: 'Marky Mark'
};
var norbert = {
    email: 'norbert@zulip.com',
    user_id: 5,
    full_name: 'Norbert Oswald'
};

global.people.add(alice);
global.people.add(fred);
global.people.add(jill);
global.people.add(mark);
global.people.add(norbert);

activity.presence_info = {};
activity.presence_info[alice.user_id] = {status: activity.IDLE};
activity.presence_info[fred.user_id] = {status: activity.ACTIVE};
activity.presence_info[jill.user_id] = {status: activity.ACTIVE};
activity.presence_info[mark.user_id] = {status: activity.IDLE};
activity.presence_info[norbert.user_id] = {status: activity.ACTIVE};

// console.info(activity.presence_info);

(function test_presence_list_full_update() {
    var users = activity.update_users();
    assert.deepEqual(users, [
        { name: 'Fred Flintstone',
          email: 'fred@zulip.com',
          num_unread: 0,
          type: 'active',
          type_desc: 'is active',
          mobile: undefined },
        { name: 'Jill Hill',
          email: 'jill@zulip.com',
          num_unread: 0,
          type: 'active',
          type_desc: 'is active',
          mobile: undefined },
        { name: 'Norbert Oswald',
          email: 'norbert@zulip.com',
          num_unread: 0,
          type: 'active',
          type_desc: 'is active',
          mobile: undefined },
        { name: 'Alice Smith',
          email: 'alice@zulip.com',
          num_unread: 0,
          type: 'idle',
          type_desc: 'is not active',
          mobile: undefined },
        { name: 'Marky Mark',
          email: 'mark@zulip.com',
          num_unread: 0,
          type: 'idle',
          type_desc: 'is not active',
          mobile: undefined }
    ]);
}());

(function test_presence_list_partial_update() {
    activity.presence_info[alice.user_id] = {status: 'active'};
    activity.presence_info[mark.user_id] = {status: 'active'};

    var users = {};

    users[alice.user_id] = {status: 'active'};
    users = activity.update_users(users);
    assert.deepEqual(users, [
        { name: 'Alice Smith',
          email: 'alice@zulip.com',
          num_unread: 0,
          type: 'active',
          type_desc: 'is active',
          mobile: undefined }
    ]);

    // Test if user index in presence_info is the expected one
    var all_users = activity._filter_and_sort(activity.presence_info);
    assert.equal(all_users.indexOf(alice.user_id.toString()), 0);

    // Test another user
    users = {};
    users[mark.user_id] = {status: 'active'};
    users = activity.update_users(users);
    assert.deepEqual(users, [
        { name: 'Marky Mark',
          email: 'mark@zulip.com',
          num_unread: 0,
          type: 'active',
          type_desc: 'is active',
          mobile: undefined }
    ]);

    all_users = activity._filter_and_sort(activity.presence_info);
    assert.equal(all_users.indexOf(mark.user_id.toString()), 3);

}());
