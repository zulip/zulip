/*
    This test suite is designed to find errors
    in our initialization sequence.  It doesn't
    really validate any behavior, other than just
    making sure things don't fail.  For more
    directed testing of individual modules, you
    should create dedicated test suites.

    Also, we stub a lot of initialization here that
    is tricky to test due to dependencies on things
    like jQuery.  A good project is to work through
    ignore_modules and try to make this test more
    complete.

    Also, it's good to be alert here for things
    that can be cleaned up in the code--for example,
    not everything needs to happen in `initialization`--
    some things can happen later in a `launch` method.

*/
set_global('i18n', global.stub_i18n);
set_global('document', {
    location: {
        protocol: 'http',
    },
});

global.patch_builtin('window', {});

set_global('csrf_token', 'whatever');

set_global('$', () => {});
set_global('resize', {});
set_global('feature_flags', {});
set_global('page_params', {});
set_global('templates', {});

const ignore_modules = [
    'activity',
    'click_handlers',
    'compose_pm_pill',
    'copy_and_paste',
    'drafts',
    'emoji',
    'emoji_picker',
    'gear_menu',
    'hashchange',
    'hotspots',
    'message_scroll',
    'message_viewport',
    'night_mode',
    'panels',
    'popovers',
    'reload',
    'scroll_bar',
    'server_events',
    'settings_sections',
    'settings_panel_menu',
    'settings_toggle',
    'subs',
    'timerender',
    'ui',
    'unread_ui',
];

_.each(ignore_modules, (mod) => {
    set_global(mod, {
        initialize: () => {},
    });
});


zrequire('util');

util.is_mobile = () => false;
templates.render = () => 'some-html';

zrequire('echo');
zrequire('colorspace');
zrequire('stream_color');
zrequire('stream_edit');
zrequire('color_data');
zrequire('stream_data');
zrequire('muting');
zrequire('condense');
zrequire('lightbox');
zrequire('overlays');
zrequire('invite');
zrequire('tab_bar');
zrequire('narrow_state');
zrequire('people');
zrequire('search_pill_widget');
zrequire('user_groups');
zrequire('unread');
zrequire('bot_data');
zrequire('message_fetch');
zrequire('marked', 'third/marked/lib/marked');
zrequire('fenced_code');
zrequire('markdown');
zrequire('upload');
zrequire('compose');
zrequire('composebox_typeahead');
zrequire('narrow');
zrequire('search');
zrequire('tutorial');
zrequire('notifications');
zrequire('pointer');
zrequire('compose_fade');
zrequire('pm_list');
zrequire('list_cursor');
zrequire('keydown_util');
zrequire('stream_sort');
zrequire('stream_list');
zrequire('topic_list');
zrequire('topic_zoom');
zrequire('sent_messages');
zrequire('typing');
zrequire('top_left_corner');
zrequire('starred_messages');
zrequire('user_status');
zrequire('user_status_ui');
zrequire('ui_init');

set_global('$', global.make_zjquery());

const document_stub = $.create('document-stub');
document.to_$ = () => document_stub;
document_stub.on = () => {};
document_stub.idle = () => {};

const window_stub = $.create('window-stub');
window.to_$ = () => window_stub;
window_stub.idle = () => {};

ui_init.initialize_kitchen_sink_stuff = () => {};

page_params.realm_default_streams = [];
page_params.subscriptions = [];
page_params.unsubscribed = [];
page_params.never_subscribed = [];
page_params.realm_notifications_stream_id = -1;

$('#tab_bar').append = () => {};
$('#compose').filedrop = () => {};

server_events.home_view_loaded = () => true;

resize.watch_manual_resize = () => {};

$("#stream_message_recipient_stream").typeahead = () => {};
$("#stream_message_recipient_topic").typeahead = () => {};
$("#private_message_recipient").typeahead = () => {};
$("#compose-textarea").typeahead = () => {};
$("#search_query").typeahead = () => {};


const value_stub = $.create('value');
const count_stub = $.create('count');
count_stub.set_find_results('.value', value_stub);
$(".top_left_starred_messages").set_find_results('.count', count_stub);


run_test('initialize_everything', () => {
    ui_init.initialize_everything();
});
