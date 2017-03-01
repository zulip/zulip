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

function stub_timestamp(model, timestamp, func) {
    var original_func = model.getTimestamp;
    model.getTimestamp = function () {
        return timestamp;
    };
    func();
    model.getTimestamp = original_func;
}

var draft_1 = {
    stream: "stream",
    subject: "topic",
    type: "stream",
    content: "Test Stream Message",
};
var draft_2 = {
    private_message_recipient: "aaron@zulip.com",
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
         stub_timestamp(draft_model, 1, function () {
             var expected = draft_1;
             expected.updatedAt = 1;
             var id = draft_model.addDraft(draft_1);

             assert.deepEqual(ls.get("drafts")[id], expected);
         });
    }());

    localStorage.clear();
    (function test_editDraft() {
         stub_timestamp(draft_model, 2, function () {
             ls.set("drafts", { id1: draft_1 } );
             var expected = draft_2;
             expected.updatedAt = 2;
             draft_model.editDraft("id1", draft_2);

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
