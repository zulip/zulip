var alert_words_ui = (function () {

var exports = {};

exports.render_alert_words_ui = function () {
    var alert_words = page_params.alert_words;
    var word_list = $('#alert_words_list');

    word_list.find('.alert-word-item').remove();
    _.each(alert_words, function (alert_word) {
        var rendered_alert_word = templates.render('alert_word_settings_item',
                                                   {word: alert_word, editing: false});
        word_list.append(rendered_alert_word);
    });
    var new_alert_word_form = templates.render('alert_word_settings_item',
                                               {word: '', editing: true});
    word_list.append(new_alert_word_form);

    // Focus new alert word name text box.
    $('#create_alert_word_name').focus();
};

function update_alert_word_status(status_text, is_error) {
    var alert_word_status = $('#alert_word_status');
    if (is_error) {
        alert_word_status.removeClass('alert-success').addClass('alert-danger');
    } else {
        alert_word_status.removeClass('alert-danger').addClass('alert-success');
    }
    alert_word_status.find('.alert_word_status_text').text(status_text);
    alert_word_status.show();
}

function update_alert_words() {
    var words = _.map($('.alert-word-item'), function (e) {
        return $(e).data('word').toString();
    });
    words = _.filter(words, function (word) {
        return word !== "";
    });
    channel.post({
        url: '/json/users/me/alert_words',
        idempotent: true,
        data: {alert_words: JSON.stringify(words)}});
}

function add_alert_word(word, event) {
    if ($.trim(word) === '') {
        update_alert_word_status(i18n.t("Alert words can't be empty!"), true);
        return;
    }
    var final_li = templates.render('alert_word_settings_item', {word: word, editing: false});

    var li = $(event.target).parents('li');
    li.replaceWith(final_li);

    var new_word = templates.render('alert_word_settings_item', {word: '', editing: true});
    var word_list = $('#alert_words_list');
    word_list.append(new_word);

    if (word_list.find('input').length > 0) {
        word_list.find('input').focus();
    }

    update_alert_words();
}

exports.set_up_alert_words = function () {
    // The settings page must be rendered before this function gets called.

    exports.render_alert_words_ui();

    $('#alert_words_list').on('click', '#create_alert_word_button', function (event) {
        var word = $('#create_alert_word_name').val();
        add_alert_word(word, event);
    });

    $('#alert_words_list').on('click', '.remove-alert-word', function (event) {
        var li = $(event.currentTarget).parents('li');
        li.remove();

        update_alert_words();
    });

    $('#alert_words_list').on('keypress', '#create_alert_word_name', function (event) {
        var key = event.which;
        // Handle enter (13) as "add".
        if (key === 13) {
            event.preventDefault();

            var word = $(event.target).val();
            add_alert_word(word, event);
        }
    });

    $('#alert-word-settings').on('click', '.close-alert-word-status', function (event) {
        event.preventDefault();
        var alert = $(event.currentTarget).parents('.alert');
        alert.hide();
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = alert_words_ui;
}
