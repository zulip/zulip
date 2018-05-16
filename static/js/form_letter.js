var form_letter = (function () {

var exports = {};

exports.activate = function (opts) {
    var self = {};

    var elem = opts.elem;
    var data = opts.extra_data;

    function make_plain_token(token) {
        var span = $('<span>');
        span.text(token.name);
        return {
            input: span,
            output: function () {
                return span.text();
            },
        };
    }

    function make_input_token(token) {
        var span = $('<input type="text">');
        span.text(token.field);
        return {
            input: span,
            output: function () {
                return span.val();
            },
        };
    }

    function make_token(token) {
        var type = token.type || 'plain';

        switch (type) {
            case 'plain':
                return make_plain_token(token);
            case 'input':
                return make_input_token(token);
        }
    }

    function make_multiple_choice_form(choice) {
        var form = $('<div>');

        var button = $('<button>');
        button.text(choice.shortcut);
        form.append(button);
        form.append('&nbsp;');

        var answer = $('<span>');
        answer.text(choice.answer);
        form.append(answer);

        button.on('click', function (e) {
            e.stopPropagation();
            var content = choice.reply;
            transmit.reply_message({
                message: opts.message,
                content: content,
            });
        });

        return form;
    }

    function make_token_form(choice) {
        var form = $('<div>');

        var token_widgets = _.map(choice.tokens, make_token);

        _.each(token_widgets, function (w) {
            form.append(w.input);
            form.append('&nbsp;');
        });

        var button = $('<button>');
        button.text(i18n.t('send'));
        form.append(button);

        button.on('click', function (e) {
            e.stopPropagation();
            var content = _.map(token_widgets, function (w) {
                return w.output();
            }).join(' ');

            transmit.reply_message({
                message: opts.message,
                content: content,
            });
        });

        return form;
    }

    function make_form(choice) {
        if (choice.type === 'multiple_choice') {
            return make_multiple_choice_form(choice);
        }

        if (choice.tokens) {
            return make_token_form(choice);
        }
    }

    function make_choices(data) {
        var widget = $('<div>');
        var lst = $('<ul>');

        if (data.heading) {
            var heading = $('<div>').text(data.heading);
            widget.append(heading);
        }

        _.each(data.choices, function (choice) {
            var item = $('<li>');
            var form = make_form(choice);
            item.append(form);
            lst.append(item);
        });

        widget.append(lst);
        return widget;
    }

    function render() {
        var widget;
        if (data.type === 'choices') {
            widget = make_choices(data);
            elem.html(widget);
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
    module.exports = form_letter;
}
