import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "../channel.ts";
import * as util from "../util.ts";
// Main JavaScript file for the integrations development panel at
// /devtools/integrations.

// Data segment: We lazy load the requested fixtures from the backend
// as and when required and then cache them here.

const fixture_schema = z.record(
    z.string(),
    z.object({
        body: z.unknown(),
        headers: z.record(z.string(), z.string()),
    }),
);

type Fixtures = z.infer<typeof fixture_schema>;

type HTMLSelectOneElement = HTMLSelectElement & {type: "select-one"};

type ClearHandlers = {
    stream_name: string;
    topic_name: string;
    URL: string;
    results_notice: string;
    bot_name: () => void;
    integration_name: () => void;
    fixture_name: () => void;
    fixture_body: () => void;
    custom_http_headers: () => void;
    results: () => void;
};

const integrations_api_response_schema = z.object({
    msg: z.string(),
    responses: z.array(
        z.object({
            status_code: z.number(),
            message: z.string(),
            fixture_name: z.optional(z.string()),
        }),
    ),
    result: z.string(),
});

type ServerResponse = z.infer<typeof integrations_api_response_schema>;

const loaded_fixtures = new Map<string, Fixtures>();
const url_base = "/api/v1/external/";

// A map defining how to clear the various UI elements.
const clear_handlers: ClearHandlers = {
    stream_name: "#stream_name",
    topic_name: "#topic_name",
    URL: "#URL",
    results_notice: "#results_notice",
    bot_name() {
        const bot_option = $<HTMLSelectOneElement>("select:not([multiple])#bot_name").children()[0];
        assert(bot_option instanceof HTMLOptionElement);
        bot_option.selected = true;
    },
    integration_name() {
        const integration_option = $<HTMLSelectOneElement>(
            "select:not([multiple])#integration_name",
        ).children()[0];
        assert(integration_option instanceof HTMLOptionElement);
        integration_option.selected = true;
    },
    fixture_name() {
        $("#fixture_name").empty();
    },
    fixture_body() {
        util.the($<HTMLTextAreaElement>("textarea#fixture_body")).value = "";
    },
    custom_http_headers() {
        util.the($<HTMLTextAreaElement>("textarea#custom_http_headers")).value = "{}";
    },
    results() {
        util.the($<HTMLTextAreaElement>("textarea#idp-results")).value = "";
    },
};

function clear_elements(elements: (keyof ClearHandlers)[]): void {
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

function set_results_notice(msg: string, level: "warning" | "success"): void {
    $("#results_notice").text(msg).css("color", results_notice_level_to_color_map[level]);
}

function get_api_key_from_selected_bot(): string {
    return $<HTMLSelectOneElement>("select:not([multiple])#bot_name").val()!;
}

function get_selected_integration_name(): string {
    return $<HTMLSelectOneElement>("select:not([multiple])#integration_name").val()!;
}

function get_fixture_format(fixture_name: string): string | undefined {
    return fixture_name.split(".").at(-1);
}

function get_custom_http_headers(): string | undefined {
    let custom_headers = $<HTMLTextAreaElement>("textarea#custom_http_headers").val()!;
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

function set_results(response: ServerResponse): void {
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
    util.the($<HTMLTextAreaElement>("textarea#idp-results")).value = data;
}

function load_fixture_body(fixture_name: string): void {
    /* Given a fixture name, use the loaded_fixtures dictionary to set
     * the fixture body field. */
    const integration_name = get_selected_integration_name();
    const fixture = loaded_fixtures.get(integration_name)![fixture_name];
    assert(fixture !== undefined);
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
    assert(typeof fixture_body === "string");
    util.the($<HTMLTextAreaElement>("textarea#fixture_body")).value = fixture_body;
    util.the($<HTMLTextAreaElement>("textarea#custom_http_headers")).value = JSON.stringify(
        headers,
        null,
        4,
    );

    return;
}

function load_fixture_options(integration_name: string): void {
    /* Using the integration name and loaded_fixtures object to set
    the fixture options for the fixture_names dropdown and also set
    the fixture body to the first fixture by default. */
    const fixtures_options_dropdown = util.the(
        $<HTMLSelectOneElement>("select:not([multiple])#fixture_name"),
    );
    const fixtures = loaded_fixtures.get(integration_name);
    assert(fixtures !== undefined);
    const fixtures_names = Object.keys(fixtures).sort();

    for (const fixture_name of fixtures_names) {
        const new_dropdown_option = document.createElement("option");
        new_dropdown_option.value = fixture_name;
        new_dropdown_option.textContent = fixture_name;
        fixtures_options_dropdown.add(new_dropdown_option);
    }
    assert(fixtures_names[0] !== undefined);
    load_fixture_body(fixtures_names[0]);

    return;
}

function update_url(): void {
    /* Construct the URL that the webhook should be targeting, using
    the bot's API key and the integration name.  The stream and topic
    are both optional, and for the sake of completeness, it should be
    noted that the topic is irrelevant without specifying the
    stream. */
    const url_field = $<HTMLInputElement>("input#URL")[0];

    const integration_name = get_selected_integration_name();
    const api_key = get_api_key_from_selected_bot();
    assert(typeof api_key === "string");
    if (integration_name === "" || api_key === "") {
        clear_elements(["URL"]);
    } else {
        const params = new URLSearchParams({api_key});
        const stream_name = $<HTMLInputElement>("input#stream_name").val()!;
        if (stream_name !== "") {
            params.set("stream", stream_name);
            const topic_name = $<HTMLInputElement>("input#topic_name").val()!;
            if (topic_name !== "") {
                params.set("topic", topic_name);
            }
        }
        const url = `${url_base}${integration_name}?${params.toString()}`;
        url_field!.value = url;
    }

    return;
}

// API callers: These methods handle communicating with the Python backend API.
function handle_unsuccessful_response(response: JQuery.jqXHR): void {
    const parsed = z.object({msg: z.string()}).safeParse(response.responseJSON);
    if (parsed.data) {
        const status_code = response.status;
        set_results_notice(`Result: (${status_code}) ${parsed.data.msg}`, "warning");
    } else {
        // If the response is not a JSON response, then it is probably
        // Django returning an HTML response containing a stack trace
        // with useful debugging information regarding the backend
        // code.
        set_results_notice(response.responseText, "warning");
    }
    return;
}

function get_fixtures(integration_name: string): void {
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
    void channel.get({
        url: "/devtools/integrations/" + integration_name + "/fixtures",
        success(raw_response) {
            const response = z
                .object({
                    result: z.string(),
                    msg: z.string(),
                    fixtures: fixture_schema,
                })
                .parse(raw_response);

            loaded_fixtures.set(integration_name, response.fixtures);
            load_fixture_options(integration_name);
            return;
        },
        error: handle_unsuccessful_response,
    });

    return;
}

function send_webhook_fixture_message(): void {
    /* Make sure that the user is sending valid JSON in the fixture
    body and that the URL is not empty. Then simply send the fixture
    body to the target URL. */

    // Note: If the user just logged in to a different Zulip account
    // using another tab while the integrations dev panel is open,
    // then the csrf token that we have stored in the hidden input
    // element would have been expired, leading to an error message
    // when the user tries to send the fixture body.
    const csrftoken = $<HTMLInputElement>("input#csrftoken").val()!;

    const url = $("#URL").val();
    if (url === "") {
        set_results_notice("URL can't be empty.", "warning");
        return;
    }

    let body = $<HTMLTextAreaElement>("textarea#fixture_body").val()!;
    const fixture_name = $<HTMLSelectOneElement>("select:not([multiple])#fixture_name").val();
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

    void channel.post({
        url: "/devtools/integrations/check_send_webhook_fixture_message",
        data: {url, body, custom_headers, is_json},
        beforeSend(xhr) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        },
        success(raw_response) {
            // If the previous fixture body was sent successfully,
            // then we should change the success message up a bit to
            // let the user easily know that this fixture body was
            // also sent successfully.
            const response = integrations_api_response_schema.parse(raw_response);
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

function send_all_fixture_messages(): void {
    /* Send all fixture messages for a given integration. */
    const url = $("#URL").val();
    const integration = get_selected_integration_name();
    if (integration === "") {
        set_results_notice("You have to select an integration first.", "warning");
        return;
    }

    const csrftoken = $<HTMLInputElement>("input#csrftoken").val()!;
    void channel.post({
        url: "/devtools/integrations/send_all_webhook_fixture_messages",
        data: {url, integration_name: integration},
        beforeSend(xhr) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        },
        success(raw_response) {
            const response = integrations_api_response_schema.parse(raw_response);
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

    util.the($<HTMLInputElement>("input#stream_name")).value = "Denmark";
    util.the($<HTMLInputElement>("input#topic_name")).value = "Integrations testing";

    const potential_default_bot = util.the(
        $<HTMLSelectOneElement>("select:not([multiple])#bot_name"),
    )[1];
    assert(potential_default_bot instanceof HTMLOptionElement);
    if (potential_default_bot !== undefined) {
        potential_default_bot.selected = true;
    }

    $<HTMLSelectOneElement>("select:not([multiple])#integration_name").on("change", function () {
        clear_elements(["custom_http_headers", "fixture_body", "fixture_name", "results_notice"]);
        const integration_name = $(this.selectedOptions).val()!;
        get_fixtures(integration_name);
        update_url();
        return;
    });

    $<HTMLSelectOneElement>("select:not([multiple])#fixture_name").on("change", function () {
        clear_elements(["fixture_body", "results_notice"]);
        const fixture_name = $(this.selectedOptions).val()!;
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
