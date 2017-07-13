set_global('$', global.make_zjquery());
set_global('window', {});

add_dependencies({
    localstorage: 'js/localstorage',
    drafts: 'js/drafts',
    Filter: 'js/filter.js',
});

var ls_container = {};
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
             ls.set("drafts", { id1: draft_1 } );
             var expected = _.clone(draft_2);
             expected.updatedAt = 2;
             draft_model.editDraft("id1", _.clone(draft_2));

             assert.deepEqual(ls.get("drafts").id1, expected);
         });
    }());

    localStorage.clear();
    (function test_deleteDraft() {
         ls.set("drafts", { id1: draft_1 } );
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
    var message_content = $("#new_message_content");
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

(function test_drafts_overlay_open() {
    var overlay = $("#draft_overlay");
    assert(!drafts.drafts_overlay_open());
    overlay.addClass("show");
    assert(drafts.drafts_overlay_open());
}());

(function test_draft_matching_narrow() {
    global.stream_data = {
            get_name: function (a) {
                return a;
            },
    };
    var stream_draft_1 = {
        stream: "stream",
        subject: "topic",
        type: "stream",
        content: "This is a msg",
    };
    var stream_draft_2 = {
        stream: "other_stream",
        subject: "topic",
        type: "stream",
        content: "This is an old msg",
    };
    var pm_draft_1 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Hi, I'm Aaron",
    };
    var pm_draft_2 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Hi, I think I'm aaron",
    };
    var draft_model = drafts.draft_model;
    draft_model.addDraft(pm_draft_2);
    draft_model.addDraft(stream_draft_2);
    draft_model.addDraft(stream_draft_1);
    draft_model.addDraft(pm_draft_1);

    // Make sure we took the most recent matching message
    var draft = drafts.draft_matching_narrow([{operator: 'pm-with', operand: 'aaron@zulip.com'}]);
    assert.equal(draft_model.getDraft(draft).content, "Hi, I'm Aaron");

    // Now test streams
    draft = drafts.draft_matching_narrow([
        {operator: 'stream', operand: 'stream'},
        {operator: 'topic', operand: 'topic'},
    ]);
    assert.equal(draft_model.getDraft(draft).content, "This is a msg");

    // Make sure we don't bother restoring old drafts
    draft = drafts.draft_matching_narrow([
        {operator: 'stream', operand: 'other_stream'},
        {operator: 'topic', operand: 'topic'},
    ]);
    assert.equal(draft_model.getDraft(draft), false);

    // Don't restore with extra operators
    draft = drafts.draft_matching_narrow([
        {operator: 'stream', operand: 'stream'},
        {operator: 'topic', operand: 'topic'},
        {operator: 'is', operand: 'starred'},
    ]);
    assert.equal(draft_model.getDraft(draft), false);

    draft = drafts.draft_matching_narrow([
        {operator: 'pm-with', operand: 'aaron@zulip.com'},
        {operator: 'is', operand: 'starred'},
    ]);
    assert.equal(draft_model.getDraft(draft), false);

    // Make sure we don't restore when the user is already typing something
    $("#new_message_content").val("Currently typing");
    draft = drafts.draft_matching_narrow([{operator: 'pm-with', operand: 'aaron@zulip.com'}]);
    assert.equal(draft_model.getDraft(draft), false);
}());
