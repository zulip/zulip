var zform = (function () {

var exports = {};

function div(opts) {
    return $('<div>').append(opts.contents);
}

function ul(opts) {
    var elem = $('<ul>');
    elem.append(opts.contents);
    elem.css('padding', '3px');
    return elem;
}

function li(opts) {
    var elem = $('<li>');
    elem.append(opts.contents);
    elem.css('list-style', 'none');
    elem.css('padding', '2px');
    return elem;
}

function text_div(txt) {
    return $('<div>').text(txt);
}

function make_button(opts) {
    var elem = $('<button>');

    elem.text(opts.text);
    elem.css('font-weight', '600');

    elem.on('click', function (e) {
        e.stopPropagation();
        opts.on_click();
    });

    return elem;
}

exports.validate_extra_data = function (data) {
    function check(data) {
        function check_choice_data(data) {
            function check_choice_item(field_name, val) {
                return schema.check_record(field_name, val, {
                    short_name: schema.check_string,
                    long_name: schema.check_string,
                    reply: schema.check_string,
                });
            }

            function check_choices(field_name, val) {
                return schema.check_array(
                    field_name,
                    val,
                    check_choice_item
                );
            }

            return schema.check_record('zform data', data, {
                heading: schema.check_string,
                choices: check_choices,
            });
        }

        if (data.type === 'choices') {
            return check_choice_data(data);
        }

        return 'unknown zform type: ' + data.type;
    }


    var msg = check(data);

    if (msg) {
        blueslip.warn(msg);
        return false;
    }

    return true;
};

exports.activate = function (opts) {
    var self = {};

    var elem = opts.elem;
    var data = opts.extra_data;

    if (!exports.validate_extra_data(data)) {
        // callee will log reason we fail
        return;
    }

    function make_choice_item(choice) {
        var button = make_button({
            text: choice.short_name,
            on_click: function () {
                var content = choice.reply;
                transmit.reply_message({
                    message: opts.message,
                    content: content,
                });
            },
        });

        var spacer = '&nbsp;';

        var long_name = $('<span>');
        long_name.text(choice.long_name);

        return div({
            contents: [button, spacer, long_name],
        });
    }

    function make_form(choice) {
        if (choice.type === 'multiple_choice') {
            return make_choice_item(choice);
        }
    }

    function make_choices(data) {
        var heading = text_div(data.heading);

        var items = _.map(data.choices, function (choice) {
            return li({
                contents: make_form(choice),
            });
        });

        var lst = ul({
            contents: items,
        });

        return div({
            contents: [heading, lst],
        });
    }

    function render() {
        var rendered_widget;

        if (data.type === 'choices') {
            rendered_widget = make_choices(data);
            elem.html(rendered_widget);
        }
    }

    self.handle_events = function (events) {
        if (events) {
            blueslip.info('unexpected');
        }
        render();
    };

    render();

    return self;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = zform;
}
