var alert_words_ui = (function () {

var exports = {};

exports.render_alert_words_ui = function () {
    var words = alert_words.words;
    var word_list = $('#alert_words_list');

    word_list.find('.alert-word-item').remove();
    _.each(words, function (alert_word) {
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

function add_alert_word(alert_word) {
    alert_word = $.trim(alert_word);
    if (alert_word === '') {
        update_alert_word_status(i18n.t("Alert word can't be empty!"), true);
        return;
    } else if (alert_words.words.indexOf(alert_word) !== -1) {
        update_alert_word_status(i18n.t("Alert word already exists!"), true);
        return;
    }

    var words_to_be_added = [alert_word];

    channel.post({
        url: '/json/users/me/alert_words',
        data: {alert_words: JSON.stringify(words_to_be_added)},
        success: function () {
            update_alert_word_status(i18n.t("Alert word added successfully!"), false);
        },
        error: function () {
            update_alert_word_status(i18n.t("Error adding alert word!"), true);
        },
    });
}

function remove_alert_word(alert_word) {
    var words_to_be_removed = [alert_word];

    channel.del({
        url: '/json/users/me/alert_words',
        data: {alert_words: JSON.stringify(words_to_be_removed)},
        success: function () {
            update_alert_word_status(i18n.t("Alert word removed successfully!"), false);
        },
        error: function () {
            update_alert_word_status(i18n.t("Error removing alert word!"), true);
        },
    });
}

exports.set_up_alert_words = function () {
    // The settings page must be rendered before this function gets called.

    exports.render_alert_words_ui();

    $('#alert_words_list').on('click', '#create_alert_word_button', function () {
        var word = $('#create_alert_word_name').val();
        add_alert_word(word);
    });

    $('#alert_words_list').on('click', '.remove-alert-word', function (event) {
        var word = $(event.currentTarget).parents('li').find('.value').text();
        remove_alert_word(word);
    });

    $('#alert_words_list').on('keypress', '#create_alert_word_name', function (event) {
        var key = event.which;
        // Handle enter (13) as "add".
        if (key === 13) {
            event.preventDefault();

            var word = $(event.target).val();
            add_alert_word(word);
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
window.alert_words_ui = alert_words_ui;
