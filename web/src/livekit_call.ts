import $ from "jquery";
import assert from "minimalistic-assert";

import {page_params as base_page_params} from "./base_page_params.ts";
import {run_prejoin} from "./livekit_call_prejoin.ts";
import {start_in_call} from "./livekit_call_room.ts";

assert(base_page_params.page_type === "livekit_call");
const page_params = base_page_params;

export async function initialize(): Promise<void> {
    const prejoin_result = await run_prejoin(page_params.is_video_call);
    if (prejoin_result === null) {
        return;
    }
    await start_in_call(
        {
            livekit_url: page_params.livekit_url,
            token: page_params.token,
            is_video_call: page_params.is_video_call,
        },
        prejoin_result,
    );
}

$(() => {
    void initialize();
});
