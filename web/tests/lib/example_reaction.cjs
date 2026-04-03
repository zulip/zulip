"use strict";

const EMOJI_CODE_MAP = {
    smile: "1f604",
    frown: "1f641",
    tada: "1f389",
    rocket: "1f680",
    wave: "1f44b",
    "8ball": "1f3b1",
    airplane: "2708",
    "+1": "1f44d",
    thumbs_up: "1f44d",
};

exports.make_reaction = (opts = {}) => {
    const emoji_name = opts.emoji_name ?? "smile";
    const emoji_code = opts.emoji_code ?? EMOJI_CODE_MAP[emoji_name] ?? "1f604";
    return {
        emoji_name,
        emoji_code,
        reaction_type: "unicode_emoji",
        user_id: opts.user_id ?? 1,
        ...opts,
    };
};
