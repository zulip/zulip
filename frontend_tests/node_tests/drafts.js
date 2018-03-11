set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);
set_global('window', {});

zrequire('localstorage');
zrequire('drafts');
zrequire('XDate', 'xdate');
zrequire('timerender');
zrequire('Handlebars', 'handlebars');
zrequire('util');

var ls_container = {};
var noop = function () { return; };

set_global('localStorage', {
    getItem: function (key) {
        return ls_container[key];
    },
    setItem: function (key, val) {
        ls_container[key] = val;
    },
    removeItem: function (key) {
        delete ls_container[key];
    },
    clear: function () {
        ls_container = {};
    },
});
set_global('compose', {});
set_global('compose_state', {});
set_global('stream_data', {
    get_color: function () {
        return '#FFFFFF';
    },
});
set_global('blueslip', {});
set_global('people', {
    // Mocking get_by_email function, here we are
    // just returning string before `@` in email
    get_by_email: function (email) {
        return {
            full_name: email.split('@')[0],
        };
    },
});
set_global('templates', {});
set_global('markdown', {
    apply_markdown: noop,
});
set_global('page_params', {
    twenty_four_hour_time: false,
});

function stub_timestamp(timestamp, func) {
    var original_func = Date.prototype.getTime;
    Date.prototype.getTime = function () {
        return timestamp;
    };
    func();
    Date.prototype.getTime = original_func;
}

var draft_1 = {
    stream: "stream",
    subject: "topic",
    type: "stream",
    content: "Test Stream Message",
};
var draft_2 = {
    private_message_recipient: "aaron@zulip.com",
    reply_to: "aaron@zulip.com",
    type: "private",
    content: "Test Private Message",
};

(function test_draft_model() {
    var draft_model = drafts.draft_model;
    var ls = localstorage();

    localStorage.clear();
    (function test_get() {
        var expected = { id1: draft_1, id2: draft_2 };
        ls.set("drafts", expected);

        assert.deepEqual(draft_model.get(), expected);
    }());

    localStorage.clear();
    (function test_get() {
        ls.set("drafts", { id1: draft_1 });

        assert.deepEqual(draft_model.getDraft("id1"), draft_1);
        assert.equal(draft_model.getDraft("id2"), false);
    }());

    localStorage.clear();
    (function test_addDraft() {
         stub_timestamp(1, function () {
             var expected = _.clone(draft_1);
             expected.updatedAt = 1;
             var id = draft_model.addDraft(_.clone(draft_1));

             assert.deepEqual(ls.get("drafts")[id], expected);
         });
    }());

    localStorage.clear();
    (function test_editDraft() {
         stub_timestamp(2, function () {
             ls.set("drafts", { id1: draft_1 });
             var expected = _.clone(draft_2);
             expected.updatedAt = 2;
             draft_model.editDraft("id1", _.clone(draft_2));

             assert.deepEqual(ls.get("drafts").id1, expected);
         });
    }());

    localStorage.clear();
    (function test_deleteDraft() {
         ls.set("drafts", { id1: draft_1 });
         draft_model.deleteDraft("id1");

         assert.deepEqual(ls.get("drafts"), {});
    }());
}());

(function test_snapshot_message() {
    function stub_draft(draft) {
        global.compose_state.get_message_type = function () {
            return draft.type;
        };
        global.compose_state.composing = function () {
            return !!draft.type;
        };
        global.compose_state.message_content = function () {
            return draft.content;
        };
        global.compose_state.recipient = function () {
            return draft.private_message_recipient;
        };
        global.compose_state.stream_name = function () {
            return draft.stream;
        };
        global.compose_state.subject = function () {
            return draft.subject;
        };
    }

    stub_draft(draft_1);
    assert.deepEqual(drafts.snapshot_message(), draft_1);

    stub_draft(draft_2);
    assert.deepEqual(drafts.snapshot_message(), draft_2);

    stub_draft({});
    assert.equal(drafts.snapshot_message(), undefined);
}());

(function test_initialize() {
    var message_content = $("#compose-textarea");
    message_content.focusout = function (f) {
        assert.equal(f, drafts.update_draft);
        f();
    };

    global.window.addEventListener = function (event_name, f) {
        assert.equal(event_name, "beforeunload");
        var called = false;
        drafts.update_draft = function () { called = true; };
        f();
        assert(called);
    };

    drafts.initialize();
}());

(function test_remove_old_drafts() {
    var draft_3 = {
        stream: "stream",
        subject: "topic",
        type: "stream",
        content: "Test Stream Message",
        updatedAt: Date.now(),
    };
    var draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test Private Message",
        updatedAt: new Date().setDate(-30),
    };
    var draft_model = drafts.draft_model;
    var ls = localstorage();
    localStorage.clear();
    var data = {id3: draft_3, id4: draft_4};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    drafts.remove_old_drafts();
    assert.deepEqual(draft_model.get(), {id3: draft_3});
}());

(function test_format_drafts() {
    draft_1.updatedAt = new Date(1549958107000).getTime();      // 2/12/2019 07:55:07 AM (UTC+0)
    draft_2.updatedAt = new Date(1549958107000).setDate(-1);
    var draft_3 = {
        stream: "stream 2",
        subject: "topic",
        type: "stream",
        content: "Test Stream Message 2",
        updatedAt: new Date(1549958107000).setDate(-10),
    };
    var draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test Private Message 2",
        updatedAt: new Date(1549958107000).setDate(-5),
    };
    var draft_5 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "zoe@zulip.com",
        type: "private",
        content: "Test Private Message 3",
        updatedAt: new Date(1549958107000).setDate(-2),
    };

    var expected = {
        id3: {
            draft_id: 'id3',
            is_stream: true,
            stream: 'stream 2',
            stream_color: '#FFFFFF',
            topic: 'topic',
            raw_content: 'Test Stream Message 2',
            time_stamp: 'Jan 21',
        },
        id4: {
            draft_id: 'id4',
            is_stream: false,
            recipients: 'aaron',
            raw_content: 'Test Private Message 2',
            time_stamp: 'Jan 26',
        },
        id5: {
            draft_id: 'id5',
            is_stream: false,
            recipients: 'aaron',
            raw_content: 'Test Private Message 3',
            time_stamp: 'Jan 29',
        },
        id2: {
            draft_id: 'id2',
            is_stream: false,
            recipients: 'aaron',
            raw_content: 'Test Private Message',
            time_stamp: 'Jan 30',
        },
        id1: {
            draft_id: 'id1',
            is_stream: true,
            stream: 'stream',
            stream_color: '#FFFFFF',
            topic: 'topic',
            raw_content: 'Test Stream Message',
            time_stamp: '7:55 AM',
        },
    };

    blueslip.error = noop;
    $('#drafts_table').append = noop;

    var draft_model = drafts.draft_model;
    var ls = localstorage();
    localStorage.clear();
    var data = { id1: draft_1, id2: draft_2, id3: draft_3, id4: draft_4, id5: draft_5 };
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    var stub_render_now = timerender.render_now;
    timerender.render_now = function (time) {
        return stub_render_now(time, new XDate(1549958107000));
    };

    global.templates.render = function (template_name, data) {
        assert.equal(template_name, 'draft_table_body');
        // Tests formatting and sorting of drafts
        assert.deepEqual(data.drafts, expected);
        return '<draft table stub>';
    };

    drafts.setup_page();
    timerender.render_now = stub_render_now;
}());
