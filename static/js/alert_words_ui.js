$(function () {
    var word_list = $('#word-alerts');
    _.each(alert_words.words, function (word) {
        var li = templates.render('alert_word_settings_item', {'word': word});
        word_list.append(li);
    });
    var new_word = templates.render('alert_word_settings_item', {'word': '', editing: true});
    word_list.append(new_word);

    function update_word_alerts() {
        var words = _.map($('.alert-word-item'), function (e) {
            return $(e).data('word');
        });
        words = _.filter(words, function (word) {
            return word !== "";
        });

        $.ajax({
            type: 'POST',
            url: '/json/set_alert_words',
            data: {alert_words: JSON.stringify(words)},
            dataType: 'json'});
    }

    function add_alert_word(word) {
          if (word === '') {
            return;
        }

        var final_li = templates.render('alert_word_settings_item', {'word': word, editing: false});

        var li = $(event.target).parent();
        li.replaceWith(final_li);

        var new_word = templates.render('alert_word_settings_item', {'word': '', editing: true});
        word_list.append(new_word);

        if (word_list.find('input').length > 0) {
            word_list.find('input').focus();
        }

        update_word_alerts();
    }

    $('#word-alerts').on('click', '.add-alert-word', function (event) {
        var word = $(event.target).siblings('input').val();
        add_alert_word(word);
    });

    $('#word-alerts').on('click', '.remove-alert-word', function (event) {
        var li = $(event.currentTarget).parent();
        li.remove();

        update_word_alerts();
    });

    $('#word-alerts').on('keypress', '.edit-alert-word', function (event) {
        var key = event.which;
        // Handle enter (13) as "add".
        if (key === 13) {
            event.preventDefault();

            var word = $(event.target).val();
            add_alert_word(word);
        }
    });
});

