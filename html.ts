export class Bool {
    label: string;
    b: boolean;

    constructor(label: string, b: boolean) {
        this.label = label;
        this.b = b;
    }

    to_source(): string {
        return this.label;
    }
}

class TrustedVar {
    label: string;

    constructor(label: string) {
        this.label = label;
    }

    to_source(): string {
        return `{{${this.label}}}`;
    }
}

export function trusted_var(label: string): TrustedVar {
    return new TrustedVar(label);
}

class TrustedSimpleString {
    s: string;

    constructor(s: string) {
        this.s = s;
    }

    to_source(): string {
        return this.s;
    }
}

export function trusted_simple_string(s: string): TrustedString {
    return new TrustedSimpleString(s);
}

export class TrustedIfElseString {
    bool : Bool;
    yes_val: TrustedString;
    no_val: TrustedString;

    constructor(
        bool: Bool,
        yes_val: TrustedString,
        no_val: TrustedString,
    ) {
        this.bool = bool;
        this.yes_val = yes_val;
        this.no_val = no_val;
    }

    to_source(): string {
        const b = this.bool.to_source();
        const yes = this.yes_val.to_source();
        const no = this.no_val.to_source();
        return `{{#if ${b}}}${yes}{{else}}${no}{{/if}}`
    }
}

type TrustedString = TrustedSimpleString | TrustedIfElseString | TrustedVar;

export class Attr {
    k: string;
    v: TrustedString;

    constructor(k: string, v: TrustedString) {
        this.k = k;
        this.v = v;
    }

    to_source(): string {
        return `${this.k}="${this.v.to_source()}"`;
    }
}

interface TagSpec {
    class_first: boolean;
    classes: TrustedString[];
    attrs: Attr[];
};

class Tag {
    tag: string;
    class_first: boolean;
    classes: TrustedString[];
    attrs: Attr[];

    constructor(tag: string, tag_spec: TagSpec) {
        this.tag = tag;
        this.class_first = tag_spec.class_first;
        this.classes = tag_spec.classes;
        this.attrs = tag_spec.attrs;
    }

    to_source(): string {
        let start_tag = "<" + this.tag;

        const classes = this.classes;
        const attrs = this.attrs;

        function add_classes() {
            if (classes.length > 0) {
                const class_frags = [];
                for (const c of classes) {
                    class_frags.push(c.to_source());
                }
                const full_class = class_frags.join(" ")
                start_tag += ` class="${full_class}"`;
            }
        }

        function add_attrs() {
            for (const attr of attrs) {
                start_tag += " " + attr.to_source();
            }
        }

        if (this.class_first) {
            add_classes();
            add_attrs();
        } else {
            add_attrs();
            add_classes();
        }

        start_tag += ">";
        return start_tag + `</${this.tag}>`;
    }
}

export function i_tag(tag_spec: TagSpec): Tag {
    return new Tag("i", tag_spec);
}

export function h5_tag(tag_spec: TagSpec): Tag {
    return new Tag("h5", tag_spec);
}

export function span_tag(tag_spec: TagSpec): Tag {
    return new Tag("span", tag_spec);
}

export class Block {
    tags: Tag[];

    constructor(tags: Tag[]) {
        this.tags = tags;
    }

    to_source(indent: string = "") {
        let source = "";
        for (const tag of this.tags) {
            source += indent + tag.to_source() + "\n";
        }
        return source;
    }
}