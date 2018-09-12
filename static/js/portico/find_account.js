function validateEmail(email) {
    var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(email);
}

function update() {
    var values = document.getElementById('emails').value.split(',');
    var check = 1;
    for (var i = 0; i < values.length ; i += 1) {
        if (validateEmail(values[i])) {
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
    {
        var submitButton = document.getElementById('submit_button');
        if (submitButton) {
            submitButton.disabled = true;
        }
        var emailsInputBox = document.getElementById('emails');
        if (emailsInputBox) {
            emailsInputBox.addEventListener('keyup' , update);
        }
    }
};
