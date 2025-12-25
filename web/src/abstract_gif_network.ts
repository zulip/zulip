export type GifInfoUrl = {
    preview_url: string;
    insert_url: string;
};

export type RenderGifsCallback = (urls: GifInfoUrl[], next_page: boolean) => void;
