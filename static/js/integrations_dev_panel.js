(function () {


// Data Segment: We lazy load the requested fixtures from the backend as and when required
// and then keep them here.
var loaded_fixtures = {};
var url_base = "/api/v1/external/";


// Resetting/Clearing: a method and a map for clearing certain UI elements.
var clear_handlers = {
    stream_name: "#stream_name",
    topic_name: "#topic_name",
    URL: "#URL",
    message: "#message",
    bot_name: function () { $('#bot_name').children()[0].selected = true; },
    integration_name: function () { $('#integration_name').children()[0].selected = true; },
    fixture_name: function () { $('#fixture_name').empty(); },
    fixture_body: function () { $("#fixture_body")[0].value = ""; },
    custom_http_headers: function () { $("#custom_http_headers")[0].value = ""; },
};

function clear_elements(elements) {
    /* Clear UI elements by specifying which ones to clear as an array of strings. */
    elements.forEach(function (element_name) {
        var handler = clear_handlers[element_name];
        if (typeof handler === "string") {
            // Handle clearing text input fields or the message field.
            var element_object = $(handler)[0];
            element_object.value = "";
            element_object.innerHTML = "";
        } else {
            // Use the function returned by the map directly.
            handler();
        }
    });
    return;
}


// Message handlers: The message is a small paragraph at the bottom of the page where
// we let the user know what happened - e.g. success, invalid JSON, etc.
var message_level_to_color_map = {
    warning: "#be1931",
    success: "#085d44",
};

function set_message(msg, level) {
    var message_field = $("#message")[0];
    message_field.innerHTML = msg;
    message_field.style.color = message_level_to_color_map[level];
    return;
}


// Helper methods
function get_api_key_from_selected_bot() {
    return $("#bot_name").children("option:selected").val();
}

function get_selected_integration_name() {
    return $("#integration_name").children("option:selected").val();
}

function get_custom_http_headers() {
    var custom_headers = $("#custom_http_headers").val();
    if (custom_headers !== "") {
        // JSON.parse("") would trigger an error, as empty strings do not qualify as JSON.
        try {
            // Let JavaScript validate the JSON for us.
            custom_headers = JSON.stringify(JSON.parse(custom_headers));
        } catch (err) {
            set_message("Custom HTTP headers are not in a valid JSON format.", "warning");
            return;
        }
    }
    return custom_headers;
}

function load_fixture_body(fixture_name) {
    /* Given a fixture name, use the loaded_fixtures dictionary to set the fixture body field. */
    var integration_name = get_selected_integration_name();
    var element = loaded_fixtures[integration_name][fixture_name];
    var fixture_body = JSON.stringify(element, null, 4); // 4 is for the pretty print indent factor.

    if (fixture_body === undefined) {
        set_message("Fixture does not have a body.", "warning");
        return;
    }
    $("#fixture_body")[0].value = fixture_body;

    return;
}

function load_fixture_options(integration_name) {
    /* Using the integration name and loaded_fixtures object to set the fixture options for the
    fixture_names dropdown and also set the fixture body to the first fixture by default. */
    var fixtures_options_dropdown = $("#fixture_name")[0];
    var fixtures_names = Object.keys(loaded_fixtures[integration_name]);

    fixtures_names.forEach(function (fixture_name) {
        var new_dropdown_option = document.createElement("option");
        new_dropdown_option.value = fixture_name;
        new_dropdown_option.innerHTML = fixture_name;
        fixtures_options_dropdown.add(new_dropdown_option);
    });
    load_fixture_body(fixtures_names[0]);

    return;
}

function update_url() {
    /* Automatically build the URL that the webhook should be targeting. To generate this URL, we
    would need at least the bot's API Key and the integration name. The stream and topic are both
    optional, and for the sake of completeness, it should be noted that the topic is irrelavent
    without specifying the stream.*/
    var url_field = $("#URL")[0];

    var integration_name = get_selected_integration_name();
    var api_key = get_api_key_from_selected_bot();

    if (integration_name === "" || api_key === "") {
        clear_elements(["URL"]);
    } else {
        var url = url_base + integration_name + "?api_key=" + api_key;
        var stream_name = $("#stream_name").val();
        if (stream_name !== "") {
            url += "&stream=" + stream_name;
            var topic_name = $("#topic_name").val();
            if (topic_name !== "") {
                url += "&topic=" + topic_name;
            }
        }
        url_field.value = url;
        url_field.innerHTML = url;
    }

    return;
}


// API Callers: These methods handle communicating with the Python backend API.
function handle_unsuccessful_response(response) {
    try {
        var status_code = response.statusCode().status;
        response = JSON.parse(response.responseText);
        set_message("Result: " + "(" + status_code + ") " + response.msg, "warning");
    } catch (err) {
        // If the response is not a JSON response then it would be Django sending a HTML response
        // containing a stack trace and useful debugging information regarding the backend code.
        document.write(response.responseText);
    }
    return;
}

function get_fixtures(integration_name) {
    /* Request fixtures from the backend for any integrations that we don't already have fixtures
    for (which would be stored in the JS variable called "loaded_fixtures"). */
    if (integration_name === "") {
        clear_elements(["custom_http_headers", "fixture_body", "fixture_name", "URL", "message"]);
        return;
    }

    if (loaded_fixtures[integration_name] !== undefined) {
        load_fixture_options(integration_name);
        return;
    }

    // We don't have the fixutures for this integration; fetch them using Zulip's channel library.
    // Relative url pattern: /devtools/integrations/(?P<integration_name>.+)/fixtures
    channel.get({
        url: "/devtools/integrations/" + integration_name + "/fixtures",
        idempotent: false,  // Since the user may add or modify fixtures while testing.
        success: function (response) {
            loaded_fixtures[integration_name] = response.fixtures;
            load_fixture_options(integration_name);
            return;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

function send_webhook_fixture_message() {
    /* Make sure that the user is sending valid JSON in the fixture body and that the URL is not
    empty. Then simply send the fixture body to the specified URL. */

    // Note: If the user has just logged in using a seperate tab while the integrations dev panel is
    // open, then the csrf token that we have stored in the hidden input element would be obsoleted
    // leading to an error message when the user tries to send the fixture body.
    var csrftoken = $("#csrftoken").val();

    var url = $("#URL").val();
    if (url === "") {
        set_message("URL can't be empty.", "warning");
        return;
    }

    var body = $("#fixture_body").val();
    try {
        // Let JavaScript validate the JSON for us.
        body = JSON.stringify(JSON.parse(body));
    } catch (err) {
        set_message("Invalid JSON in fixture body.", "warning");
        return;
    }

    var custom_headers = get_custom_http_headers();

    channel.post({
        url: "/devtools/integrations/check_send_webhook_fixture_message",
        data: {url: url, body: body, custom_headers: custom_headers},
        beforeSend: function (xhr) {xhr.setRequestHeader('X-CSRFToken', csrftoken);},
        success: function () {
            // If the previous fixture body was sent successfully, then we should change the success
            // message up a bit to let the user easily know that this fixture body was also sent
            // successfully.
            if ($("#message")[0].innerHTML === "Success!") {
                set_message("Success!!!", "success");
            } else {
                set_message("Success!", "success");
            }
            return;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

function send_all_fixture_messages() {
    /* Send all fixture messages for a given integration. */
    var url = $("#URL").val();
    var integration = get_selected_integration_name();
    if (integration === "") {
        set_message("You have to select an integration first.");
        return;
    }

    var custom_headers = get_custom_http_headers();

    var csrftoken = $("#csrftoken").val();
    channel.post({
        url: "/devtools/integrations/send_all_webhook_fixture_messages",
        data: {url: url, custom_headers: custom_headers, integration_name: integration},
        beforeSend: function (xhr) {xhr.setRequestHeader('X-CSRFToken', csrftoken);},
        success: function (response) {
            // This is a somewhat sloppy construction, but ultimately, it's a devtool.
            var responses = response.responses;
            var data = "Results:\n\n";
            responses.forEach(function (response) {
                data += "Fixture:            " + response.fixture_name + "\nStatus Code:    ";
                data += response.status_code + "\nResponse:       " + response.message + "\n\n";
            });
            $("#fixture_body")[0].value = data;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

// Initialization
$(function () {
    clear_elements(["stream_name", "topic_name", "URL", "bot_name", "integration_name",
                    "fixture_name", "custom_http_headers", "fixture_body", "message"]);

    $("#stream_name")[0].value = "Denmark";
    $("#topic_name")[0].value = "Integrations Testing";

    var potential_default_bot = $("#bot_name")[0][1];
    if (potential_default_bot !== undefined) {
        potential_default_bot.selected = true;
    }

    $('#integration_name').change(function () {
        clear_elements(["custom_http_headers", "fixture_body", "fixture_name", "message"]);
        var integration_name = $(this).children("option:selected").val();
        get_fixtures(integration_name);
        update_url();
        return;
    });

    $('#fixture_name').change(function () {
        clear_elements(["fixture_body", "message"]);
        var fixture_name = $(this).children("option:selected").val();
        load_fixture_body(fixture_name);
        return;
    });

    $('#send_fixture_button').click(function () {
        send_webhook_fixture_message();
        return;
    });

    $('#send_all_fixtures_button').click(function () {
        send_all_fixture_messages();
        return;
    });

    $("#bot_name").change(update_url);

    $("#stream_name").change(update_url);

    $("#topic_name").change(update_url);

});

}());

/*
Development Notes:
 - We currently don't support non-json fixtures.

Possible Improvements:
 - Add support for extra keys, headers, etc.
*/
