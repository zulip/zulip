/*
This is an incomplete stub, which we include here because
we only use parts of the marked API and are using a fork
of the upstream library.
*/

import { PrimitiveValue } from "url-template";

export class Renderer {
    code: (code: string) => string;
    link: (href: string, title: string, text: string) => string;
    br: () => string;
}

export type RegExpOrStub = RegExp | {
    exec(string: string): RegExpExecArray | null;
};

export type LinkifierMatch = PrimitiveValue | PrimitiveValue[] | Record<string, PrimitiveValue>;

export type ParseOptions = {
    get_linkifier_regexes: () => RegExp[];
    linkifierHandler: (pattern: RegExp, matches: LinkifierMatch[]) => string;
    emojiHandler: (emoji_name: string) => string;
    unicodeEmojiHandler: (unicode_emoji: string) => string;
    streamHandler: (stream_name: string) => string | undefined;
    streamTopicHandler: (stream_name: string, topic: string) => string | undefined;
    texHandler: (tex: string, fullmatch: string) => string;
    timestampHandler: (time_string: string) => string;
    gfm: boolean;
    tables: boolean;
    breaks: boolean;
    pedantic: boolean;
    sanitize: boolean;
    smartLists: boolean;
    smartypants: boolean;
    zulip: boolean;
    renderer: Renderer;
    preprocessors: ((src: string) => string)[];
};

type MarkedOptions = ParseOptions & {
    userMentionHandler: (mention: string, silently: boolean) => string | undefined;
    groupMentionHandler: (name: string, silently: boolean) => string | undefined;
    silencedMentionHandler: (quote: string) => string;
};

declare const marked: {
    // Note: We don't use the `callback` option in any of our code.
    (src: string, opt: MarkedOptions, callback?: any): string;
    Lexer: {
        rules: {
            tables: {
                newline: RegExpOrStub;
                code: RegExpOrStub;
                fences: RegExpOrStub;
                hr: RegExpOrStub;
                heading: RegExpOrStub;
                nptable: RegExpOrStub;
                blockquote: RegExpOrStub;
                list: RegExpOrStub;
                html: RegExpOrStub;
                def: RegExpOrStub;
                table: RegExpOrStub;
                paragraph: RegExpOrStub;
                text: RegExpOrStub;
                bullet: RegExpOrStub;
                item: RegExpOrStub;
                _ta: RegExpOrStub;
            };
        };
    };
    InlineLexer: {
        rules: {
            zulip: {
                escape: RegExpOrStub;
                autolink: RegExpOrStub;
                url: RegExpOrStub;
                tag: RegExpOrStub;
                link: RegExpOrStub;
                reflink: RegExpOrStub;
                nolink: RegExpOrStub;
                strong: RegExpOrStub;
                em: RegExpOrStub;
                code: RegExpOrStub;
                br: RegExpOrStub;
                del: RegExpOrStub;
                emoji: RegExpOrStub;
                unicodeemoji: RegExpOrStub;
                usermention: RegExpOrStub;
                groupmention: RegExpOrStub;
                stream: RegExpOrStub;
                tex: RegExpOrStub;
                timestamp: RegExpOrStub;
                text: RegExpOrStub;
                _inside: RegExpOrStub;
                _href: RegExpOrStub;
                stream_topic: RegExpOrStub;
            };
        };
    };
    Renderer: typeof Renderer;
    stashHtml: (html: string, safe: boolean) => string;
};

export default marked;
