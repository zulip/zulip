set_global('$', function () {});
set_global('document', {
    hasFocus: function () {
        return true;
    }
});
set_global('feature_flags', {});
set_global('page_params', {
    people_list: []
});


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

global.$ = require('jQuery');
$.fn.expectOne = function () {
    assert(this.length === 1);
    return this;
};

global.use_template('user_presence_row');
global.use_template('user_presence_rows');

var people = require("js/people.js");
var activity = require('js/activity.js');
activity.presence_info = {
    'alice@zulip.com': {status: activity.IDLE},
    'fred@zulip.com': {status: activity.ACTIVE},
    'jill@zulip.com': {status: activity.ACTIVE},
    'mark@zulip.com': {status: activity.IDLE},
    'norbert@zulip.com': {status: activity.ACTIVE}
};

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
