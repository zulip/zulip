import assert from "minimalistic-assert";

import * as bot_data from "./bot_data.ts";
import {realm} from "./state_data.ts";

export function generate_zuliprc_url(bot_id: number): string {
    const bot = bot_data.get(bot_id);
    assert(bot !== undefined);
    const data = generate_zuliprc_content(bot);
    return encode_zuliprc_as_url(data);
}

export function encode_zuliprc_as_url(zuliprc: string): string {
    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(zuliprc);
}

export function generate_zuliprc_content(bot: {
    bot_type?: number;
    user_id: number;
    email: string;
    api_key: string;
}): string {
    let token;
    // For outgoing webhooks, include the token in the zuliprc.
    // It's needed for authenticating to the Botserver.
    if (bot.bot_type === 3) {
        const services = bot_data.get_services(bot.user_id);
        assert(services !== undefined);
        const service = services[0];
        assert(service && "token" in service);
        token = service.token;
    }
    return (
        "[api]" +
        "\nemail=" +
        bot.email +
        "\nkey=" +
        bot.api_key +
        "\nsite=" +
        realm.realm_url +
        (token === undefined ? "" : "\ntoken=" + token) +
        // Some tools would not work in files without a trailing new line.
        "\n"
    );
}
