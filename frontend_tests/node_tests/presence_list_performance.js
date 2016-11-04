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
activity.presence_info = {
    'alice@zulip.com': {status: activity.IDLE},
    'fred@zulip.com': {status: activity.ACTIVE},
    'jill@zulip.com': {status: activity.ACTIVE},
    'mark@zulip.com': {status: activity.IDLE},
    'norbert@zulip.com': {status: activity.ACTIVE}
};


// TODO: de-dup with activity.js
global.people.add({
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith'
});
global.people.add({
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone"
});
global.people.add({
    email: 'jill@zulip.com',
    user_id: 3,
    full_name: 'Jill Hill'
});
global.people.add({
    email: 'mark@zulip.com',
    user_id: 4,
    full_name: 'Marky Mark'
});
global.people.add({
    email: 'norbert@zulip.com',
    user_id: 5,
    full_name: 'Norbert Oswald'
});

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
    var users = {
        'alice@zulip.com': {status: 'active'}
    };
    activity.presence_info['alice@zulip.com'] = users['alice@zulip.com'];

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
    assert.equal(all_users.indexOf('alice@zulip.com'), 0);

    // Test another user
    users = {
        'mark@zulip.com': {status: 'active'}
    };
    activity.presence_info['mark@zulip.com'] = users['mark@zulip.com'];
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
    assert.equal(all_users.indexOf('mark@zulip.com'), 3);

}());
