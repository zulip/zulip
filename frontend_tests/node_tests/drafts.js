global.stub_out_jquery();

add_dependencies({
    localstorage: 'js/localstorage',
    drafts: 'js/drafts',
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
