var widgetize = (function () {

var exports = {};

var widgets = {};

widgets.poll = poll_widget;
widgets.tictactoe = tictactoe_widget;
widgets.todo = todo_widget;
widgets.zform = zform;

var widget_contents = {};
exports.widget_contents = widget_contents;

function set_widget_in_message(row, widget_elem) {
    var content_holder = row.find('.message_content');
    content_holder.empty().append(widget_elem);
}

exports.activate = function (in_opts) {
    var widget_type = in_opts.widget_type;
    var extra_data = in_opts.extra_data;
    var events = in_opts.events;
    var row = in_opts.row;
    var message = in_opts.message;
    var post_to_server = in_opts.post_to_server;

    events.shift();

    if (!widgets[widget_type]) {
        blueslip.warn('unknown widget_type', widget_type);
        return;
    }

    var callback = function (data) {
        post_to_server({
            msg_type: 'widget',
            data: data,
        });
    };

    if (row.attr('id').startsWith('zhome') && narrow_state.active()) {
        // Don't place widget in a home message row if we are narrowed
        // to active state
        return;
    }

    var widget_elem = widget_contents[message.id];
    if (widget_elem) {
        set_widget_in_message(row, widget_elem);
        return;
    }

    // We depend on our widgets to use templates to build
    // the HTML that will eventually go in this div.
    widget_elem = $('<div>').addClass('widget-content');

    widgets[widget_type].activate({
        elem: widget_elem,
        callback: callback,
        message: message,
        extra_data: extra_data,
    });

    widget_contents[message.id] = widget_elem;
    set_widget_in_message(row, widget_elem);

    // Replay any events that already happened.  (This is common
    // when you narrow to a message after other users have already
    // interacted with it.)
    if (events.length > 0) {
        widget_elem.handle_events(events);
    }
};

exports.set_widgets_for_list = function () {
    _.each(widget_contents, function (widget_elem, idx) {
        if (current_msg_list.get(idx) !== undefined) {
            var row = current_msg_list.get_row(idx);
            set_widget_in_message(row, widget_elem);
        }
    });
};

exports.handle_event = function (widget_event) {
    var widget_elem = widget_contents[widget_event.message_id];

    if (!widget_elem) {
        // It is common for submessage events to arrive on
        // messages that we don't yet have in view. We
        // just ignore them completely here.
        return;
    }

    var events = [widget_event];

    widget_elem.handle_events(events);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = widgetize;
}

window.widgetize = widgetize;
