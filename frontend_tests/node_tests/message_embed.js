"use strict";

set_global("$", global.make_zjquery());
set_global("channel", {});
zrequire("message_embed");
zrequire("rows");

run_test("remove_preview", () => {
    const message_row = $.create("msg-row-stub");
    const remove_preview_button = $.create("remove-preview-stub");
    const embed = $.create("embed-stub");
    const url = $.create("url-stub");
    const link = "http://zulipchat.com";

    url.attr("href", link);
    embed.set_find_results("a", url);
    remove_preview_button.set_parent(embed);
    remove_preview_button.set_parents_result(".message_row", message_row);
    message_row.attr("zid", "100");
    message_row.set_find_results(".restore-draft", []);

    channel.post = function (opts) {
        assert.equal(opts.url, "/json/messages/100/remove_preview");
        assert.equal(opts.data.message_id, 100);
        assert.equal(opts.data.url, link);
        opts.success();
    };
    message_embed.remove_preview(remove_preview_button);
});
