set_global('$', global.make_zjquery());

zrequire('settings_muting');
zrequire('stream_data');
zrequire('muting');
set_global('muting_ui', {});

var noop = function () {};

var frontend = {
    stream_id: 101,
    name: 'frontend',
};
stream_data.add_sub('frontend', frontend);

run_test('settings', () => {

    muting.add_muted_topic(frontend.stream_id, 'js');
    var set_up_ui_called = false;
    muting_ui.set_up_muted_topics_ui = function (opts) {
        assert.deepEqual(opts, [[frontend.stream_id, 'js']]);
        set_up_ui_called = true;
    };

    settings_muting.set_up();

    var click_handler = $('body').get_on_handler('click', '.settings-unmute-topic');
    assert.equal(typeof click_handler, 'function');

    var event = {
        stopImmediatePropagation: noop,
    };

    var fake_this = $.create('fake.settings-unmute-topic');
    var tr_html = $('tr[data-topic="js"]');
    fake_this.closest = function (opts) {
        assert.equal(opts, 'tr');
        return tr_html;
    };

    var data_called = 0;
    tr_html.attr = function (opts) {
        if (opts === 'data-stream-id') {
            data_called += 1;
            return frontend.stream_id;
        }
        if (opts === 'data-topic') {
            data_called += 1;
            return 'js';
        }
    };

    var unmute_called = false;
    muting_ui.unmute = function (stream_id, topic) {
        assert.equal(stream_id, frontend.stream_id);
        assert.equal(topic, 'js');
        unmute_called = true;
    };
    click_handler.call(fake_this, event);
    assert(unmute_called);
    assert(set_up_ui_called);
    assert.equal(data_called, 2);
});
