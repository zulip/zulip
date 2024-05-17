import $ from "jquery";

import * as channel from "../channel";
// Main JavaScript file for the integrations development panel at
// /devtools/integrations.

// Data segment: We lazy load the requested fixtures from the backend
// as and when required and then cache them here.

const loaded_fixtures = new Map();
const url_base = "/api/v1/external/";

// A map defining how to clear the various UI elements.
const clear_handlers = {
    stream_name: "#stream_name",
    topic_name: "#topic_name",
    URL: "#URL",
    results_notice: "#results_notice",
    bot_name() {
        $("#bot_name").children()[0].selected = true;
    },
    integration_name() {
        $("#integration_name").children()[0].selected = true;
    },
    fixture_name() {
        $("#fixture_name").empty();
    },
    fixture_body() {
        $("#fixture_body")[0].value = "";
    },
    custom_http_headers() {
        $("#custom_http_headers")[0].value = "{}";
    },
    results() {
        $("#idp-results")[0].value = "";
    },
};

function clear_elements(elements) {
    // Supports strings (a selector to clear) or calling a function
    // (for more complex logic).
    for (const element_name of elements) {
        const handler = clear_handlers[element_name];
        if (typeof handler === "string") {
            $(handler).val("").empty();
        } else {
            handler();
        }
    }
    return;
}

// Success/failure colors used for displaying results to the user.
const results_notice_level_to_color_map = {
    warning: "#be1931",
    success: "#085d44",
};

function set_results_notice(msg, level) {
    $("#results_notice").text(msg).css("color", results_notice_level_to_color_map[level]);
}

function get_api_key_from_selected_bot() {
    return $("#bot_name").val();
}

function get_selected_integration_name() {
    return $("#integration_name").val();
}

function get_fixture_format(fixture_name) {
    return fixture_name.split(".").at(-1);
}

function get_custom_http_headers() {
    let custom_headers = $("#custom_http_headers").val();
    if (custom_headers !== "") {
        // JSON.parse("") would trigger an error, as empty strings do not qualify as JSON.
        try {
            // Let JavaScript validate the JSON for us.
            custom_headers = JSON.stringify(JSON.parse(custom_headers));
        } catch {
            set_results_notice("Custom HTTP headers are not in a valid JSON format.", "warning");
            return undefined;
        }
    }
    return custom_headers;
}

function set_results(response) {
    /* The backend returns the JSON responses for each of the
    send_message actions included in our request (which is just 1 for
    send, but usually is several for send all).  We display these
    responses to the user in the "results" panel.

    The following is a bit messy, but it's a devtool, so ultimately OK */
    const responses = response.responses;

    let data = "Results:\n\n";
    for (const response of responses) {
        if (response.fixture_name !== undefined) {
            data += "Fixture:            " + response.fixture_name;
            data += "\nStatus code:    " + response.status_code;
        } else {
            data += "Status code:    " + response.status_code;
        }
        data += "\nResponse:       " + response.message + "\n\n";
    }
    $("#idp-results")[0].value = data;
}

function load_fixture_body(fixture_name) {
    /* Given a fixture name, use the loaded_fixtures dictionary to set
     * the fixture body field. */
    const integration_name = get_selected_integration_name();
    const fixture = loaded_fixtures.get(integration_name)[fixture_name];
    let fixture_body = fixture.body;
    const headers = fixture.headers;
    if (fixture_body === undefined) {
        set_results_notice("Fixture does not have a body.", "warning");
        return;
    }
    if (get_fixture_format(fixture_name) === "json") {
        // The 4 argument is pretty printer indentation.
        fixture_body = JSON.stringify(fixture_body, null, 4);
    }
    $("#fixture_body")[0].value = fixture_body;
    $("#custom_http_headers")[0].value = JSON.stringify(headers, null, 4);

    return;
}

function load_fixture_options(integration_name) {
    /* Using the integration name and loaded_fixtures object to set
    the fixture options for the fixture_names dropdown and also set
    the fixture body to the first fixture by default. */
    const fixtures_options_dropdown = $("#fixture_name")[0];
    const fixtures_names = Object.keys(loaded_fixtures.get(integration_name)).sort();

    for (const fixture_name of fixtures_names) {
        const new_dropdown_option = document.createElement("option");
        new_dropdown_option.value = fixture_name;
        new_dropdown_option.textContent = fixture_name;
        fixtures_options_dropdown.add(new_dropdown_option);
    }
    load_fixture_body(fixtures_names[0]);

    return;
}

function update_url() {
    /* Construct the URL that the webhook should be targeting, using
    the bot's API key and the integration name.  The stream and topic
    are both optional, and for the sake of completeness, it should be
    noted that the topic is irrelevant without specifying the
    stream. */
    const url_field = $("#URL")[0];

    const integration_name = get_selected_integration_name();
    const api_key = get_api_key_from_selected_bot();

    if (integration_name === "" || api_key === "") {
        clear_elements(["URL"]);
    } else {
        const params = new URLSearchParams({api_key});
        const stream_name = $("#stream_name").val();
        if (stream_name !== "") {
            params.set("stream", stream_name);
            const topic_name = $("#topic_name").val();
            if (topic_name !== "") {
                params.set("topic", topic_name);
            }
        }
        const url = `${url_base}${integration_name}?${params}`;
        url_field.value = url;
    }

    return;
}

// API callers: These methods handle communicating with the Python backend API.
function handle_unsuccessful_response(response) {
    if (response.responseJSON?.msg) {
        const status_code = response.statusCode().status;
        set_results_notice(`Result: (${status_code}) ${response.responseJSON.msg}`, "warning");
    } else {
        // If the response is not a JSON response, then it is probably
        // Django returning an HTML response containing a stack trace
        // with useful debugging information regarding the backend
        // code.
        document.write(response.responseText);
    }
    return;
}

function get_fixtures(integration_name) {
    /* Request fixtures from the backend for any integrations that we
    don't already have fixtures cached in loaded_fixtures). */
    if (integration_name === "") {
        clear_elements([
            "custom_http_headers",
            "fixture_body",
            "fixture_name",
            "URL",
            "results_notice",
        ]);
        return;
    }

    if (loaded_fixtures.has(integration_name)) {
        load_fixture_options(integration_name);
        return;
    }

    // We don't have the fixtures for this integration; fetch them
    // from the backend.  Relative URL pattern:
    // /devtools/integrations/<integration_name>/fixtures
    channel.get({
        url: "/devtools/integrations/" + integration_name + "/fixtures",
        success(response) {
            loaded_fixtures.set(integration_name, response.fixtures);
            load_fixture_options(integration_name);
            return;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

function send_webhook_fixture_message() {
    /* Make sure that the user is sending valid JSON in the fixture
    body and that the URL is not empty. Then simply send the fixture
    body to the target URL. */

    // Note: If the user just logged in to a different Zulip account
    // using another tab while the integrations dev panel is open,
    // then the csrf token that we have stored in the hidden input
    // element would have been expired, leading to an error message
    // when the user tries to send the fixture body.
    const csrftoken = $("#csrftoken").val();

    const url = $("#URL").val();
    if (url === "") {
        set_results_notice("URL can't be empty.", "warning");
        return;
    }

    let body = $("#fixture_body").val();
    const fixture_name = $("#fixture_name").val();
    let is_json = false;
    if (fixture_name && get_fixture_format(fixture_name) === "json") {
        try {
            // Let JavaScript validate the JSON for us.
            body = JSON.stringify(JSON.parse(body));
            is_json = true;
        } catch {
            set_results_notice("Invalid JSON in fixture body.", "warning");
            return;
        }
    }

    const custom_headers = get_custom_http_headers();

    channel.post({
        url: "/devtools/integrations/check_send_webhook_fixture_message",
        data: {url, body, custom_headers, is_json},
        beforeSend(xhr) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        },
        success(response) {
            // If the previous fixture body was sent successfully,
            // then we should change the success message up a bit to
            // let the user easily know that this fixture body was
            // also sent successfully.
            set_results(response);
            if ($("#results_notice").text() === "Success!") {
                set_results_notice("Success!!!", "success");
            } else {
                set_results_notice("Success!", "success");
            }
            return;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

function send_all_fixture_messages() {
    /* Send all fixture messages for a given integration. */
    const url = $("#URL").val();
    const integration = get_selected_integration_name();
    if (integration === "") {
        set_results_notice("You have to select an integration first.");
        return;
    }

    const csrftoken = $("#csrftoken").val();
    channel.post({
        url: "/devtools/integrations/send_all_webhook_fixture_messages",
        data: {url, integration_name: integration},
        beforeSend(xhr) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        },
        success(response) {
            set_results(response);
        },
        error: handle_unsuccessful_response,
    });

    return;
}

// Initialization
$(() => {
    clear_elements([
        "stream_name",
        "topic_name",
        "URL",
        "bot_name",
        "integration_name",
        "fixture_name",
        "custom_http_headers",
        "fixture_body",
        "results_notice",
        "results",
    ]);

    $("#stream_name")[0].value = "Denmark";
    $("#topic_name")[0].value = "Integrations testing";

    const potential_default_bot = $("#bot_name")[0][1];
    if (potential_default_bot !== undefined) {
        potential_default_bot.selected = true;
    }

    $("#integration_name").on("change", function () {
        clear_elements(["custom_http_headers", "fixture_body", "fixture_name", "results_notice"]);
        const integration_name = $(this.selectedOptions).val();
        get_fixtures(integration_name);
        update_url();
        return;
    });

    $("#fixture_name").on("change", function () {
        clear_elements(["fixture_body", "results_notice"]);
        const fixture_name = $(this.selectedOptions).val();
        load_fixture_body(fixture_name);
        return;
    });

    $("#send_fixture_button").on("click", () => {
        send_webhook_fixture_message();
        return;
    });

    $("#send_all_fixtures_button").on("click", () => {
        clear_elements(["results_notice"]);
        send_all_fixture_messages();
        return;
    });

    $("#bot_name").on("change", update_url);

    $("#stream_name").on("change", update_url);

    $("#topic_name").on("change", update_url);
});
