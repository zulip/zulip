// This reloads the module in development rather than refreshing the page
if (module.hot) {
    module.hot.accept();
}

var common = (function () {

var exports = {};

exports.status_classes = 'alert-error alert-success alert-info';

exports.autofocus = function (selector) {
    $(function () {
        $(selector).focus();
    });
};

// Return a boolean indicating whether the password is acceptable.
// Also updates a Bootstrap progress bar control (a jQuery object)
// if provided.
//
// Assumes that zxcvbn.js has been loaded.
//
// This is in common.js because we want to use it from the signup page
// and also from the in-app password change interface.
exports.password_quality = function (password, bar, score, password_field) {
    // We load zxcvbn.js asynchronously, so the variable might not be set.
    if (typeof zxcvbn === 'undefined') {
        return undefined;
    }

    var min_length = password_field.data('minLength');
    var min_guesses = password_field.data('minGuesses');

    var result = zxcvbn(password);
    var acceptable = (password.length >= min_length
                      && result.guesses >= min_guesses);

    var pw_score = [i18n.t('Very weak'),i18n.t('Weak'),i18n.t('Medium'),i18n.t('Strong'),i18n.t('Very strong')];

    if (bar !== undefined) {
        var t = result.crack_times_seconds.offline_slow_hashing_1e4_per_second;
        var bar_progress = Math.min(1, Math.log(1 + t) / 22);

        // Even if zxcvbn loves your short password, the bar should be
        // filled at most 1/3 of the way, because we won't accept it.
        if (!acceptable) {
            bar_progress = Math.min(bar_progress, 0.33);
        }

        // The bar bottoms out at 10% so there's always something
        // for the user to see.
        bar.width(((90 * bar_progress) + 10) + '%')
           .removeClass('bar-success bar-danger')
           .addClass(acceptable ? 'bar-success' : 'bar-danger');
    }

    if (score !== undefined) {
        // Display password score/strength
        score.text(pw_score[zxcvbn(password).score])
             .removeClass('text-success text-error');
        if (acceptable) {
            score.addClass('text-success');
        } else {
            score.addClass('text-error');
        }
    }

    return acceptable;
};

exports.password_warning = function (password, password_field) {
    if (typeof zxcvbn === 'undefined') {
        return undefined;
    }

    var min_length = password_field.data('minLength');
    var result = zxcvbn(password);

    if (password.length < min_length) {
        return i18n.t('Password should be at least __length__ characters long', {length: min_length});
    }

    var warning = i18n.t('__warning__ __suggestions__',{
                warning: result.feedback.warning || "Password is too weak.",
                suggestions: result.feedback.suggestions});

    return warning;
};

exports.password_crack_time = function (password, crack_time) {
    if (typeof zxcvbn === 'undefined') {
        return undefined;
    }

    var crackTime = zxcvbn(password).crack_times_display.offline_slow_hashing_1e4_per_second;

    if (crack_time !== undefined) {
        crack_time.text(i18n.t('Crack time: __time__', {time: crackTime}));
        crack_time.attr('title', i18n.t('This password can be cracked in __time__.', {time: crackTime}));
    }

    return crackTime;
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = common;
}
