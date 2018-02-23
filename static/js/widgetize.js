var widgetize = (function () {

var exports = {};

var widgets = {};

widgets.poll = voting_widget;
widgets.tictactoe = tictactoe_widget;

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

    var content_holder = row.find('.message_content');

    var widget_elem;
    if (message.widget) {
        // Use local to work around linter.  We can trust this
        // value because it comes from a template.
        widget_elem = message.widget_elem;
        content_holder.html(widget_elem);
        return;
    }

    var callback = function (data) {
        post_to_server({
            msg_type: 'widget',
            data: data,
        });
    };

    // We depend on our widgets to use templates to build
    // the HTML that will eventually go in this div.
    widget_elem = $('<div>');
    content_holder.html(widget_elem);

    var widget = widgets[widget_type].activate({
        elem: widget_elem,
        callback: callback,
        message: message,
        extra_data: extra_data,
    });

    // This is hacky, we should just maintain our own list.
    message.widget = widget;
    message.widget_elem = widget_elem;

    // Replay any events that already happened.  (This is common
    // when you narrow to a message after other users have already
    // interacted with it.)
    if (events.length > 0) {
        widget.handle_events(events);
    }
};

exports.handle_event = function (widget_event) {
    var message = message_store.get(widget_event.message_id);

    var events = [widget_event];

    message.widget.handle_events(events);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = widgetize;
}
