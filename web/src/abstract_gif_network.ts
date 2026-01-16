export type GifInfoUrl = {
    preview_url: string;
    insert_url: string;
};

export type RenderGifsCallback = (urls: GifInfoUrl[], next_page: boolean) => void;

// When a user clicks on the gif icon either while composing a
// message in the normal compose box or while editing a
// message, the UI will need to talk to a third party
// vendor such as tenor to get gifs.

// The network class will need to support this protocol.

// Typically, the UI will instantiate an object from a derived subclass
// of `GifNetwork`.
// Then they will make one or more calls to ask_for_*() to ask the
// third party to send back gif urls. See the callback
// type definition as well (RenderGifsCallback).

// The final piece of the contract is that if the user abandons the UI
// (typically the picker is a popover, but we don't care here), then
// the UI should call `abandon()` below. And then they should
// obviously never call the object again.
export abstract class GifNetwork {
    abstract is_loading_more_gifs(): boolean;
    abstract ask_for_default_gifs(
        next_page: boolean,
        render_gifs_callback: RenderGifsCallback,
    ): void;
    abstract ask_for_search_gifs(
        search_term: string,
        next_page: boolean,
        render_gifs_callback: RenderGifsCallback,
    ): void;
    abstract abandon(): void;
}
