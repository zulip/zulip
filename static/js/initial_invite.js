var initial_invite = (function () {

// invite_suffix is set by the server-side django template
// in this page
/*global invite_suffix: true */

var exports = {};

var redirect_url;
var candidates = [
    [{name: "candide", email: "candide@skeptics.com"},
     {name: "cunégonde", email: "cunégonde@westphalia.com"},
     {name: "pangloss", email: "pangloss@allforthebest.com"},
     {name: "cacambo", email: "cacambo@candide.com"},
     {name: "martin", email: "martin@candide"},
     {name: "baron.thunder-ten-tronckh", email: "baron@candide.com"},
     {name: "jacques.the.anabaptist", email: "anabaptist@candide.com"},
     {name: "the.scholar", email: "scholar@candide.com"},
     {name: "paquette", email: "paquette@candide.com"},
     {name: "signor.pococurante", email: "pocurante@candide.com"}],

    [{name: "emma.bovary", email: "emma@normandy.com"},
     {name: "charles.bovary", email: "charles@normandy.com"},
     {name: "rodolphe.boulanger", email: "rodolphe@normandy.com"},
     {name: "léon.dupuis", email: "dupuis@normandy.com"},
     {name: "monsieur.lheureux", email: "lheureux@normandy.com"},
     {name: "monsieur.homais", email: "homais@normandy.com"},
     {name: "madame.homais", email: "mme_homais@normandy.com"},
     {name: "justin", email: "justin@normandy.com"}],

    [{name: "lena.grove", email: "lena@yoknapatawpha.gov"},
     {name: "byron.bunch", email: "byron@yoknapatawpha.gov"},
     {name: "joe.christmas", email: "christmas@yoknapatawpha.gov"},
     {name: "lucas.birch", email: "birch@yoknapatawpha.gov"},
     {name: "gail.hightower", email: "gail@yoknapatawpha.gov"},
     {name: "joanna.burden", email: "burden@yoknapatawpha.gov"},
     {name: "mr.mceachern", email: "mceachern@yoknapatawpha.gov"},
     {name: "percy.grimm", email: "grimm@yoknapatawpha.gov"},
     {name: "mr.armstid ", email: "armistid@yoknapatawpha.gov"},
     {name: "bobby", email: "bobby@yoknapatawpha.gov"},
     {name: "gavin.stephens", email: "stephens@yoknapatawpha.gov"}],

    [{name: "stephen.dedalus", email: "stephen@odyssey.com"},
     {name: "buck.mulligan", email: "mulligan@odyssey.com"},
     {name: "leopold.bloom", email: "leopoldbloom@odyssey.com"},
     {name: "molly.bloom", email: "molly@odyssey.com"},
     {name: "blazes.boylan", email: "boylan@odyssey.com"},
     {name: "paddy.dignam", email: "dignan@odyssey.com"},
     {name: "milly.bloom", email: "milly@odyssey.com"},
     {name: "george.william.russell", email: "russell@odyssey.com"},
     {name: "father.john.conmee", email: "fatherconmee@odyssey.com"}],

    [{name: "yossarian", email: "yossasrian@catch22.com"},
     {name: "colonel.cathcart", email: "cathcart@catch22.com"},
     {name: "milo.minderbinder", email: "minderbinder@catch22.com"},
     {name: "chaplain.tappman", email: "tappman@catch22.com"},
     {name: "doctor.daneeka", email: "daneeka@catch22.com"},
     {name: "lieutenant.nately", email: "nately@catch22.com"},
     {name: "general.scheisskopf", email: "scheisskopf@catch22.com"},
     {name: "snowden", email: "snowden@catch22.com"},
     {name: "captain.aardvark", email: "aardvark@catch22.com"},
     {name: "captain.black", email: "black@catch22.com"}]
];
var literary_work;

function random_candidate() {
    if (literary_work === undefined || literary_work.length === 0) {
        literary_work = candidates[Math.floor(Math.random() * candidates.length)].slice(0);
        literary_work.reverse();
    }

    return literary_work.pop();
}

function set_placeholder(input_row, candidate) {
    var contents;
    if (invite_suffix !== '') {
        contents  = candidate.name;
    } else {
        contents = candidate.email;
    }
    input_row.attr('placeholder', contents);
}

function add_input_row() {
    var rows = $(".invite_row");
    if (rows.length === 0) {
        return;
    }

    var lastrow = rows[rows.length - 1];

    var input = $(lastrow).clone();
    var input_text = $('input', input);
    input_text.val('');

    // Give it a sequentially unique name, required for jquery-validate
    // to be able to target each row individually with an error
    var name = input_text.attr('name');
    var num = parseInt(name.split('_')[1], 10);
    input_text.attr('name', 'email_' + (num + 1));

    set_placeholder(input_text, random_candidate());

    $('#invite_blurb').before(input);
}

function handle_focus(e) {
    var rowdiv = $(e.target).parent();
    var prev = rowdiv.prev();

    if (prev.length === 0) {
        return;
    }

    // If the user entered some content and
    // tabs to the last entry field, add another one
    var prevInput = $(prev[0]).children('input');
    if (prevInput.val() !== "" &&
        rowdiv.nextAll('.invite_row').length === 0) {
        add_input_row();
    }
}

function is_local_part(value, element) {
    // Match an rfc2822 local part of an email address
    // Either dot notation or quoted form
    // Inspired by Django's EmailValidator
    var regex = /^(?:[a-z0-9!#$%&'*+\/=?\^_`{|}~\-]+(?:\.[a-z0-9!#$%&'*+\/=?\^_`{|}~\-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")$/i;

    return this.optional(element) || regex.test(value);
}

function get_invitee_emails() {
    var emails = [];
    _.each($('.invite_row > input'), function (elem) {
        var email = $(elem).val();

        if (email === '') {
            return;
        }

        if (invite_suffix !== "") {
            email = email + '@' + invite_suffix;
        }

        emails.push(email);
    });
    return emails;
}

$(document).ready(function () {
    $('form:first *:input[type!=hidden]:first').focus();

    var csrf_token = $('input[name="csrfmiddlewaretoken"]').attr('value');

    $("#invite_rows").on('focus', 'input', function (e) {
        handle_focus(e);
    });

    $.validator.addMethod("invite_email",
                          function (value, element) {
                            if (invite_suffix !== '') {
                                // Validate first part of email only
                              return is_local_part.call(this, value, element);
                            } else {
                                // Normal email validation for open realms
                                return true;
                            }
                          },
                          "Please enter a valid email address.");

    $("#invite_form").validate({
        errorClass: 'text-error',
        keyup: false,
        errorPlacement: function (error, element) {
            error.appendTo(element.parent('div'));
        },
        showErrors: function (errorMap, errorList) {
            if (errorList.length > 0) {
                $('#submit_invitation').attr('disabled', '');
            } else {
                $('#submit_invitation').removeAttr('disabled');
            }
            this.defaultShowErrors();
        },
        submitHandler: function (form) {
            $('#submit_invitation').attr('disabled', '');
            $('#submit_invitation').text("Inviting …");

            $.ajax({
                type: 'POST',
                dataType: 'json',
                url: '/json/bulk_invite_users',
                data: { invitee_emails: JSON.stringify(get_invitee_emails()),
                        csrfmiddlewaretoken: csrf_token },
                complete: function () {
                    // Redirect to home
                    window.location.href = "/";
                }
            });
        }
    });

    // Initial placeholder and extra rows
    set_placeholder($("input.invite_email"), random_candidate());
    add_input_row();
    add_input_row();
});

return exports;

}());
