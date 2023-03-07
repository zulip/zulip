import $ from "jquery";

export function update_padding(opts: {
    content_sel: string;
    padding_sel: string;
    total_rows: number;
    shown_rows: number;
}): void {
    const $content = $(opts.content_sel);
    const $padding = $(opts.padding_sel);
    const total_rows = opts.total_rows;
    const shown_rows = opts.shown_rows;
    const hidden_rows = total_rows - shown_rows;

    if (shown_rows === 0) {
        $padding.height(0);
        return;
    }

    const ratio = hidden_rows / shown_rows;

    const content_height = $content.height();
    if (content_height === undefined) {
        return;
    }

    const new_padding_height = ratio * content_height;

    $padding.height(new_padding_height);
    $padding.width(1);
}
