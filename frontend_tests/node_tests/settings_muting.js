set_global('$', global.make_zjquery());

zrequire('settings_muting');
zrequire('muting');
set_global('muting_ui', {});

var noop = function () {};

(function test_settings() {

    muting.add_muted_topic('frontend', 'js');
    var set_up_ui_called = false;
    muting_ui.set_up_muted_topics_ui = function (opts) {
        assert.deepEqual(opts, [['frontend', 'js']]);
        set_up_ui_called = true;
    };

    settings_muting.set_up();

    var click_handler = $('body').get_on_handler('click', '.settings-unmute-topic');
    assert.equal(typeof(click_handler), 'function');

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
    tr_html.data = function (opts) {
        if (opts === 'stream') {
            data_called += 1;
            return 'frontend';
        }
        if (opts === 'topic') {
            data_called += 1;
            return 'js';
        }
    };

    var unmute_called = false;
    muting_ui.unmute = function (stream, topic) {
        assert.equal(stream, 'frontend');
        assert.equal(topic, 'js');
        unmute_called = true;
    };
    click_handler.call(fake_this, event);
    assert(unmute_called);
    assert(set_up_ui_called);
    assert.equal(data_called, 2);
}());
