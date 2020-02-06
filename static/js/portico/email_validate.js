$(document).on('input', "#emails", function () {

    const entries = $('#emails').val();

    let emails = entries.split(/[\s]{0,},[\s]{0,}/);
    emails = emails.map(function (address) {
        // link to the regex reference https://stackoverflow.com/questions/46155/how-to-validate-an-email-address-in-javascript
        const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(address);
    });
    const valid = emails.includes(false);

    if (!valid) {
        $('#submitButton').css('background', '#313E4E');
        $('#output').val("Valid Email");
        $('#submitButton').prop('disabled', false);

    } else if (emails.length > 10) {
        $('#submitButton').css('background', '#999999');
        $('#output').val("We can check up to 10 email addresses at one time.");
        $('#submitButton').prop('disabled', true);

    } else {
        $('#submitButton').css('background', '#999999');
        $('#output').val("Invalid email");
        $('#submitButton').prop('disabled', false);
    }
});
