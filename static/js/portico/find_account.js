function validateEmail(email) {
    var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    // https://www.regular-expressions.info/email.html
    // https://stackoverflow.com/questions/46155/how-to-validate-an-email-address-in-javascript
    return re.test(email);
}

function update_submit_button_state() {
    var values = document.getElementById('emails').value.split(',');
    var check = 1;
    for (var i = 0; i < values.length; i += 1) {
        if (validateEmail(values[i].trim())) {
            check = 1;
        } else {
            check = 0;
            break;
        }
    }
    var submitButton = document.getElementById('submit_button');
    if (submitButton) {
        if (check === 1) {
            submitButton.disabled = false;
            submitButton.removeAttribute("inactive");
            submitButton.className = "active";
        } else {
            submitButton.disabled = true;
            submitButton.removeAttribute("active");
            submitButton.className = "inactive";
        }
    }
}

window.onload = function () {
    var submitButton = document.getElementById('submit_button');
    if (submitButton) {
        submitButton.disabled = true;
    }
    var emailsInputBox = document.getElementById('emails');
    if (emailsInputBox) {
        emailsInputBox.addEventListener('keyup', update_submit_button_state);
    }
};

