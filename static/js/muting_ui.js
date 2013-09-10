var muting_ui = (function () {

var exports = {};

exports.persist_and_rerender = function () {
    // Optimistically rerender our new muting preferences.  The back
    // end should eventually save it, and if it doesn't, it's a recoverable
    // error--the user can just mute the topic again, and the topic might
    // die down before the next reload anyway, making the muting moot.
    current_msg_list.rerender();
    var data = {
        muted_topics: JSON.stringify(muting.get_muted_topics())
    };
    $.ajax({
        type: 'POST',
        url: '/json/set_muted_topics',
        data: data,
        dataType: 'json'
    });
};

return exports;
}());

