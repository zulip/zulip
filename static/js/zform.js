var zform = (function () {

var exports = {};

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

    var outer_elem = opts.elem;
    var data = opts.extra_data;

    if (!exports.validate_extra_data(data)) {
        // callee will log reason we fail
        return;
    }

    function make_choices(data) {
        // Assign idx values to each of our choices so that
        // our template can create data-idx values for our
        // JS code to use later.
        _.each(data.choices, function (choice, idx) {
            choice.idx = idx;
        });

        var html = templates.render('zform-choices', data);
        var elem = $(html);

        elem.find('button').on('click', function (e) {
            e.stopPropagation();

            // Grab our index from the markup.
            var idx = $(e.target).attr('data-idx');

            // Use the index from the markup to dereference our
            // data structure.
            var reply_content = data.choices[idx].reply;

            transmit.reply_message({
                message: opts.message,
                content: reply_content,
            });
        });

        return elem;
    }

    function render() {
        var rendered_widget;

        if (data.type === 'choices') {
            rendered_widget = make_choices(data);
            outer_elem.html(rendered_widget);
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

window.zform = zform;
