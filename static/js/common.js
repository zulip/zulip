var status_classes = 'alert-error alert-success alert-info';

function autofocus(selector) {
    $(function () {
        $(selector)[0].focus();
    });
}

// Return a boolean indicating whether the password is acceptable.
// Also updates a Bootstrap progress bar control (a jQuery object)
// if provided.
//
// Assumes that zxcvbn.js has been loaded.
//
// This is in common.js because we want to use it from the signup page
// and also from the in-app password change interface.
function password_quality(password, bar) {
    // We load zxcvbn.js asynchronously, so the variable might not be set.
    if (typeof zxcvbn === 'undefined') {
        return undefined;
    }

    // Consider the password acceptable if it's at least 6 characters.
    var acceptable = password.length >= 6;

    if (bar !== undefined) {
        // Compute a quality score in [0,1].
        var result  = zxcvbn(password);
        var quality = Math.min(1,Math.log(1 + result.crack_times_seconds.
                                              offline_slow_hashing_1e4_per_second) / 22);

        // Even if zxcvbn loves your short password, the bar should be filled
        // at most 1/3 of the way, because we won't accept it.
        if (!acceptable) {
            quality = Math.min(quality, 0.33);
        }

        // Display the password quality score on a progress bar
        // which bottoms out at 10% so there's always something
        // for the user to see.
        bar.width(((90 * quality) + 10) + '%')
           .removeClass('bar-success bar-danger')
           .addClass(acceptable ? 'bar-success' : 'bar-danger');
    }

    return acceptable;
}

if (typeof module !== 'undefined') {
    module.exports.status_classes = status_classes;
    module.exports.autofocus = autofocus;
    module.exports.password_quality = password_quality;
}
