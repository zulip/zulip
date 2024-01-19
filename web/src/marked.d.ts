declare module "marked" {
    type Parser = {
        parse: (src: string, options: Marked["defaults"], renderer?: Renderer) => string;
    };
    type Renderer = (options?: Marked["defaults"]) => void;
    type Lexer = {
        (options: Marked["defaults"]): void;
        block: {
            newline: RegExp;
            code: RegExp;
            fences: () => void;
            hr: RegExp;
            heading: RegExp;
            nptable: () => void;
            blockquote: RegExp;
            list: RegExp;
            html: RegExp;
            def: RegExp;
            table: () => void;
            paragraph: RegExp;
            text: RegExp;
        };
        rules: Lexer["block"];
        lex: (src: string, options: Marked["defaults"]) => {type: string; cap: string | null};
    };
    type InlineLexerRules = {
        escape: RegExp;
        autolink: RegExp;
        url: () => void;
        tag: RegExp;
        link: RegExp;
        reflink: RegExp;
        nolink: RegExp;
        strong: RegExp;
        em: RegExp;
        code: RegExp;
        br: RegExp;
        del: () => void;
        emoji: () => void;
        unicodeemoji: () => void;
        usermention: () => void;
        groupmention: () => void;
        stream: () => void;
        tex: () => void;
        timestamp: () => void;
        text: RegExp;
        zulip: {
            emoji: RegExp;
            unicodeemoji: RegExp;
            usermention: RegExp;
            groupmention: RegExp;
            stream_topic: RegExp;
            stream: RegExp;
            tex: RegExp;
            timestamp: RegExp;
            text: RegExp;
        };
    };
    type InlineLexer = {
        (links: string, options: Marked["defaults"]): void;
        rules: InlineLexerRules;
        output: (src: string, links: string, options: Marked["defaults"]) => string;
    };

    export type Marked = {
        (src: string, opt: Marked["defaults"], callback?: unknown): void;
        defaults: {
            gfm: boolean;
            emoji: boolean;
            unicodeemoji: boolean;
            timestamp: boolean;
            tables: boolean;
            breaks: boolean;
            pedantic: boolean;
            sanitize: boolean;
            sanitizer: null;
            mangle: boolean;
            smartLists: boolean;
            silent: boolean;
            highlight: null;
            langPrefix: string;
            smartypants: boolean;
            headerPrefix: string;
            renderer: Renderer;
            preprocessors: [];
            xhtml: boolean;
        };
        Parser: Parser;
        parser: Parser["parse"];
        Renderer: Renderer;
        Lexer: Lexer;
        lexer: Lexer["lex"];
        InlineLexer: InlineLexer;
        inlineLexer: InlineLexer["output"];
        parse: Marked;
        stashHtml: (html: string, safe: unknown) => string;
    };
}
