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
    if (typeof zxcvbn === 'undefined')
        return undefined;

    var result     = zxcvbn(password);
    var acceptable = result.crack_time >= 1e5;
    var quality;

    if (bar !== undefined) {
        // Compute a quality score in [0,1].
        quality = Math.min(1, Math.log(1 + result.crack_time) / 22);

        // Display the password quality score on a progress bar
        // which bottoms out at 10% so there's always something
        // for the user to see.
        bar.width(((90 * quality) + 10) + '%')
           .removeClass('bar-success bar-danger')
           .addClass(acceptable ? 'bar-success' : 'bar-danger');
    }

    return acceptable;
}
