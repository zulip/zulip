var alert_words_ui = (function () {

var exports = {};

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
        $("#empty_alert_word_error").show();
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

    var word_list = $('#alert_words_list');
    _.each(alert_words.words, function (word) {
        var li = templates.render('alert_word_settings_item', {word: word});
        word_list.append(li);
    });
    var new_word = templates.render('alert_word_settings_item', {word: '', editing: true});
    word_list.append(new_word);

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

    $('#alert_words_list').on('click', '.close-empty-alert-word-error', function (event) {
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
