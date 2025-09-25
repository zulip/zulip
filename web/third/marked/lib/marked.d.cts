/*
This is an incomplete stub, which we include here because
we only use parts of the marked API and are using a fork
of the upstream library.
*/

import {PrimitiveValue} from "url-template";

declare class Renderer {
    code: (code: string) => string;
    link: (href: string, title: string, text: string) => string;
    br: () => string;
    image: (href: string, title: string, text: string) => string;
}

declare namespace marked {
    type RegExpOrStub =
        | RegExp
        | {
              exec(string: string): RegExpExecArray | null;
          };

    type LinkifierMatch = PrimitiveValue | PrimitiveValue[] | Record<string, PrimitiveValue>;

    type ParseOptions = {
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
}

declare const marked: {
    // Note: We don't use the `callback` option in any of our code.
    (src: string, opt: marked.MarkedOptions, callback?: any): string;
    Lexer: {
        rules: {
            tables: {
                newline: marked.RegExpOrStub;
                code: marked.RegExpOrStub;
                fences: marked.RegExpOrStub;
                hr: marked.RegExpOrStub;
                heading: marked.RegExpOrStub;
                nptable: marked.RegExpOrStub;
                blockquote: marked.RegExpOrStub;
                list: marked.RegExpOrStub;
                html: marked.RegExpOrStub;
                def: marked.RegExpOrStub;
                table: marked.RegExpOrStub;
                paragraph: marked.RegExpOrStub;
                text: marked.RegExpOrStub;
                bullet: marked.RegExpOrStub;
                item: marked.RegExpOrStub;
                _ta: marked.RegExpOrStub;
            };
        };
    };
    InlineLexer: {
        rules: {
            zulip: {
                escape: marked.RegExpOrStub;
                autolink: marked.RegExpOrStub;
                url: marked.RegExpOrStub;
                tag: marked.RegExpOrStub;
                link: marked.RegExpOrStub;
                reflink: marked.RegExpOrStub;
                nolink: marked.RegExpOrStub;
                strong: marked.RegExpOrStub;
                em: marked.RegExpOrStub;
                code: marked.RegExpOrStub;
                br: marked.RegExpOrStub;
                del: marked.RegExpOrStub;
                emoji: marked.RegExpOrStub;
                unicodeemoji: marked.RegExpOrStub;
                usermention: marked.RegExpOrStub;
                groupmention: marked.RegExpOrStub;
                stream: marked.RegExpOrStub;
                tex: marked.RegExpOrStub;
                timestamp: marked.RegExpOrStub;
                text: marked.RegExpOrStub;
                _inside: marked.RegExpOrStub;
                _href: marked.RegExpOrStub;
                stream_topic: marked.RegExpOrStub;
            };
        };
    };
    Renderer: typeof Renderer;
    stashHtml: (html: string, safe: boolean) => string;
};

export = marked;
