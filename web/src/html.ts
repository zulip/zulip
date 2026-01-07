// next few lines are just for node.js

// const {JSDOM} = require("jsdom");
// const dom = new JSDOM(`<!DOCTYPE html>`);
// const document = dom.window.document;

const void_elements = new Set([
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
]);

export type SourceFormat = "inline" | "block" | "strange_block";

export type CustomElement = {
    to_source: (indent: string) => string;
    to_dom: () => Node;
};

type TextElement = ParenthesizedTag | TextVar | TranslatedText | InputTextTag;

type Element = Tag | Comment | SorryBlock | Partial | TextElement | CustomElement;

type TrustedString =
    | TrustedSimpleString
    | TrustedIfElseString
    | TrustedIfString
    | TrustedUnlessString
    | TrustedAttrStringVar
    | TranslatedAttrValue
    | TrustedClassWithVarSuffix;

// class strings are implicitly trusted.
type ClassString = string | TrustedString;

type TagSpec = {
    classes?: ClassString[];
    attrs?: Attr[];
    children?: Element[];
    force_attrs_before_class?: boolean;
    pink?: boolean;
    source_format?: SourceFormat;
};

type BlockSpec = {
    elements: Element[];
    source_format?: SourceFormat;
};

type SimpleEachSpec = {
    each_label: string;
    loop_var_partial_label: string;
    get_blocks: () => Block[];
};

type BoolVarSpec = {label: string; b: boolean};

type TranslatedAttrValueSpec = {translated_string: string};

type TrustedIfElseStringSpec = {bool: BoolVar; yes_val: TrustedString; no_val: TrustedString};

type TrustedConditionalStringSpec = {bool: BoolVar; val: TrustedString};

type TranslatedTextSpec = {translated_text: string; force_single_quotes?: boolean; pink?: boolean};

type TrustedAttrStringVarSpec = {label: string; s: UnEscapedAttrString};

type TextVarSpec = {label: string; s: UnEscapedTextString; pink?: boolean};

type TrustedClassWithVarSuffixSpec = {prefix: string; var_suffix: TrustedAttrStringVar};

type PartialSpec = {
    inner_label: string;
    trusted_html: TrustedHtml;
    custom_context?: string;
};

function as_raw_html(frag: Node): string {
    const div = document.createElement("div");
    div.append(frag);
    return div.innerHTML;
}

function get_class_source(c: ClassString): string {
    if (typeof c === "string") {
        return c;
    }
    return c.to_source();
}

function get_class_render_val(c: ClassString): string | undefined {
    if (typeof c === "string") {
        return c;
    }
    return c.render_val();
}

function build_classes(classes: ClassString[]): string {
    if (classes.length === 0) {
        return "";
    }

    const class_frags = [];
    for (const c of classes) {
        class_frags.push(get_class_source(c));
    }
    const full_class = class_frags.join(" ");
    return ` class="${full_class}"`;
}

function build_attrs(attrs: Attr[]): string {
    let result = "";
    for (const attr of attrs) {
        result += " " + attr.to_source();
    }
    return result;
}

function text_wrapped_in_color_span(text: string, color: string): HTMLSpanElement {
    const wrapper_span = document.createElement("span");
    wrapper_span.textContent = text;
    wrapper_span.style.backgroundColor = color;
    return wrapper_span;
}

function text_wrapped_in_pink_span(text: string): HTMLSpanElement {
    return text_wrapped_in_color_span(text, "pink");
}

function text_wrapped_in_orange_span(text: string): HTMLSpanElement {
    return text_wrapped_in_color_span(text, "orange");
}

class Comment {
    comment: string;

    constructor(comment: string) {
        this.comment = comment;
    }

    to_source(indent: string): string {
        return indent + `{{!-- ${this.comment} --}}`;
    }
}

export class BoolVar {
    label: string;
    b: boolean;

    constructor(info: BoolVarSpec) {
        this.label = info.label;
        this.b = info.b;
    }

    to_source(): string {
        return this.label;
    }
}

export class TrustedAttrStringVar {
    label: string;
    s: UnEscapedAttrString;

    constructor(info: TrustedAttrStringVarSpec) {
        this.label = info.label;
        this.s = info.s;
    }

    to_source(): string {
        return `{{${this.label}}}`;
    }
    render_val(): string {
        return this.s.s.trim();
    }
}

class TrustedClassWithVarSuffix {
    var_suffix: TrustedAttrStringVar;
    // The prefix string will be used for classes like `zulip-icon`
    prefix: string;

    constructor(info: TrustedClassWithVarSuffixSpec) {
        this.var_suffix = info.var_suffix;
        this.prefix = info.prefix;
    }

    to_source(): string {
        return `${this.prefix}-${this.var_suffix.to_source()}`;
    }

    render_val(): string {
        return `${this.prefix.trim()}-${this.var_suffix.render_val()}`;
    }
}

export class TextVar {
    label: string;
    s: UnEscapedTextString;
    pink: boolean | undefined;

    constructor(info: TextVarSpec) {
        this.label = info.label;
        this.s = info.s;
        this.pink = info.pink;
    }

    to_source(indent: string): string {
        return indent + `{{${this.label}}}`;
    }

    to_dom(): Node {
        if (this.pink) {
            return text_wrapped_in_pink_span(this.s.s);
        }
        return document.createTextNode(this.s.s);
    }
}

class UnEscapedAttrString {
    s: string;

    constructor(s: string) {
        this.s = s;
    }
}

class UnEscapedTextString {
    s: string;

    constructor(s: string) {
        this.s = s;
    }
}

export class TrustedSimpleString {
    s: string;

    constructor(s: string) {
        this.s = s;
    }

    to_source(): string {
        return this.s;
    }

    render_val(): string {
        return this.to_source().trim();
    }
}

class TrustedHtml {
    html: string;

    constructor(html: string) {
        this.html = html;
    }

    to_source(indent: string): string {
        return indent + this.html;
    }

    to_dom(): DocumentFragment {
        const template = document.createElement("template");
        template.innerHTML = this.html;
        return template.content;
    }
}

class Partial {
    inner_label: string;
    trusted_html: TrustedHtml;
    // Only meant to make the `to_source` generation match with the
    // existing templates, this is supposed to be shortlived, as partials
    // themselves are transient and only relevant for migration purposes.
    context: string | undefined;

    constructor(info: PartialSpec) {
        this.inner_label = info.inner_label;
        this.trusted_html = info.trusted_html;
        this.context = info.custom_context ?? ".";
    }

    to_source(indent: string): string {
        return indent + `{{> ${this.inner_label} ${this.context}}}`;
    }

    to_dom(): DocumentFragment {
        return this.trusted_html.to_dom();
    }
}

export class SorryBlock {
    placeholder_text: string;
    // This object is useful for testing and development. It creates a stub object.
    // In development users will get a pink text span saying "sorry" that reminds them
    // to eventually implement the actual sub-component.
    // (This approach was inspired by Lean Programming's approach toward
    // iteratively building up proofs.)
    constructor(placeholder_text?: string) {
        this.placeholder_text = placeholder_text ?? "sorry";
    }
    to_source(indent: string): string {
        return indent + this.placeholder_text;
    }

    to_dom(): Node {
        return text_wrapped_in_orange_span(this.placeholder_text);
    }
}

export function format_block(info: {
    source_format: SourceFormat;
    indent: string;
    start_tag: string;
    end_tag: string;
    children: Element[];
}): string {
    const {source_format, indent, start_tag, end_tag, children} = info;

    if (source_format === "inline") {
        const inlined_block = children.map((e) => e.to_source("")).join("");
        return indent + start_tag + inlined_block + end_tag;
    }

    if (children.length === 0) {
        return indent + start_tag + "\n" + indent + end_tag;
    }

    const child_indent = source_format === "strange_block" ? indent : indent + "    ";
    const block = children.map((e) => e.to_source(child_indent)).join("\n");
    return indent + start_tag + "\n" + block + "\n" + indent + end_tag;
}

class TranslatedText {
    translated_text: string;
    force_single_quotes: boolean | undefined;
    pink: boolean | undefined;
    // We assume the caller is passing in the
    // translated version of the string (unescaped).
    constructor(info: TranslatedTextSpec) {
        this.translated_text = info.translated_text;
        this.force_single_quotes = info.force_single_quotes;
        this.pink = info.pink;
    }

    to_source(indent: string): string {
        if (this.force_single_quotes) {
            return indent + `{{t '${this.translated_text}'}}`;
        }
        return indent + `{{t "${this.translated_text}" }}`;
    }

    to_dom(): Node {
        if (this.pink) {
            return text_wrapped_in_pink_span(this.translated_text);
        }
        return document.createTextNode(this.translated_text);
    }
}

export class TrustedIfElseString {
    bool: BoolVar;
    yes_val: TrustedString;
    no_val: TrustedString;

    constructor(info: TrustedIfElseStringSpec) {
        this.bool = info.bool;
        this.yes_val = info.yes_val;
        this.no_val = info.no_val;
    }

    to_source(): string {
        const b = this.bool.to_source();
        const yes = this.yes_val.to_source();
        const no = this.no_val.to_source();
        return `{{#if ${b}}}${yes}{{else}}${no}{{/if}}`;
    }

    render_val(): string | undefined {
        if (this.bool.b) {
            return this.yes_val.render_val()?.trim();
        }
        return this.no_val.render_val()?.trim();
    }
}

class TrustedIfString {
    bool: BoolVar;
    val: TrustedString;
    constructor(info: TrustedConditionalStringSpec) {
        this.bool = info.bool;
        this.val = info.val;
    }

    to_source(): string {
        const b = this.bool.to_source();
        const val = this.val.to_source();
        return `{{#if ${b}}}${val}{{/if}}`;
    }

    render_val(): string | undefined {
        if (this.bool.b) {
            return this.val.render_val()?.trim();
        }
        return undefined;
    }
}

class TrustedUnlessString {
    bool: BoolVar;
    val: TrustedString;
    constructor(info: TrustedConditionalStringSpec) {
        this.bool = info.bool;
        this.val = info.val;
    }

    to_source(): string {
        const b = this.bool.to_source();
        const val = this.val.to_source();
        return `{{#unless ${b}}}${val}{{/unless}}`;
    }

    render_val(): string | undefined {
        if (!this.bool.b) {
            return this.val.render_val()?.trim();
        }
        return undefined;
    }
}

export class TranslatedAttrValue {
    translated_string: string;

    constructor(info: TranslatedAttrValueSpec) {
        this.translated_string = info.translated_string;
    }

    to_source(): string {
        const english_string = this.translated_string; // force this in our test code
        return `{{t '${english_string}'}}`;
    }

    render_val(): string {
        return this.translated_string.trim();
    }
}

export class Attr {
    k: string;
    v: TrustedString | TranslatedAttrValue;

    constructor(k: string, v: TrustedString | TranslatedAttrValue) {
        this.k = k;
        this.v = v;
    }

    to_source(): string {
        return `${this.k}="${this.v.to_source()}"`;
    }
}

export class Block {
    elements: Element[] = [];

    constructor(info: BlockSpec) {
        for (const member of info.elements) {
            this.elements.push(member);
        }
    }

    to_source(indent: string): string {
        let source = "";
        for (const element of this.elements) {
            source += element.to_source(indent);
            source += "\n";
        }
        return source;
    }

    to_dom(): DocumentFragment {
        const dom = document.createDocumentFragment();
        for (const element of this.elements) {
            if (element instanceof Comment) {
                continue;
            }
            dom.append(element.to_dom());
        }
        return dom;
    }

    as_raw_html(): string {
        return as_raw_html(this.to_dom());
    }
}

export class SimpleEach {
    each_label: string;
    loop_var_partial_label: string;
    get_blocks: () => Block[];

    constructor(info: SimpleEachSpec) {
        this.each_label = info.each_label;
        this.loop_var_partial_label = info.loop_var_partial_label;
        this.get_blocks = info.get_blocks;
    }

    to_source(indent: string): string {
        return (
            indent +
            `{{#each ${this.each_label}}}\n` +
            indent +
            `    {{> ${this.loop_var_partial_label} .}}\n` +
            indent +
            `{{/each}}`
        );
    }

    to_dom(): DocumentFragment {
        const dom = document.createDocumentFragment();
        for (const block of this.get_blocks()) {
            dom.append(block.to_dom());
        }
        return dom;
    }

    as_raw_html(): string {
        return as_raw_html(this.to_dom());
    }
}

export class Tag {
    tag: string;
    // Class strings are implicitly trusted
    classes: ClassString[];
    attrs: Attr[];
    children: Element[];
    force_attrs_before_class: boolean | undefined;
    pink: boolean | undefined;
    source_format: SourceFormat;

    constructor(tag: string, tag_spec: TagSpec) {
        this.tag = tag;
        this.classes = tag_spec.classes ?? [];
        this.attrs = tag_spec.attrs ?? [];
        this.children = tag_spec.children ?? [];
        this.force_attrs_before_class = tag_spec.force_attrs_before_class;
        this.pink = tag_spec.pink;
        this.source_format = tag_spec.source_format ?? this.guess_source_format();
    }

    guess_source_format(): SourceFormat {
        if (this.children.length <= 1) {
            return "inline";
        }
        return "block";
    }

    to_source(indent: string): string {
        let start_tag = `<${this.tag}`;

        if (this.force_attrs_before_class) {
            start_tag += build_attrs(this.attrs);
            start_tag += build_classes(this.classes);
        } else {
            start_tag += build_classes(this.classes);
            start_tag += build_attrs(this.attrs);
        }

        if (void_elements.has(this.tag)) {
            return indent + start_tag + "/>";
        }

        start_tag += ">";
        const end_tag = `</${this.tag}>`;

        return format_block({
            source_format: this.source_format,
            indent,
            start_tag,
            end_tag,
            children: this.children,
        });
    }

    to_dom(): HTMLElement {
        const element = document.createElement(this.tag);
        for (const el_class of this.classes) {
            const render_val = get_class_render_val(el_class);
            if (render_val) {
                element.classList.add(render_val);
            }
        }
        for (const attr of this.attrs) {
            const render_val = attr.v.render_val();
            if (render_val) {
                element.setAttribute(attr.k, render_val);
            }
        }
        element.append(new Block({elements: this.children}).to_dom());
        if (this.pink) {
            element.style.backgroundColor = "pink";
        }
        return element;
    }
}

export class InputTextTag {
    classes: ClassString[];
    attrs: Attr[];
    pink: boolean | undefined;
    constructor(info: {
        classes: ClassString[];
        attrs?: Attr[];
        placeholder_value: TranslatedAttrValue;
        pink?: boolean;
    }) {
        this.classes = info.classes;
        this.attrs = info.attrs ?? [];
        this.attrs.push(new Attr("placeholder", info.placeholder_value));
        this.pink = info.pink;
    }

    to_source(indent: string): string {
        let tag = `<input type="text"`;

        tag += build_classes(this.classes);
        tag += build_attrs(this.attrs);

        tag += " />";

        return indent + tag;
    }

    to_dom(): HTMLElement {
        const element = document.createElement("input");
        element.setAttribute("type", "text");

        for (const el_class of this.classes) {
            const render_val = get_class_render_val(el_class);
            if (render_val) {
                element.classList.add(render_val);
            }
        }

        for (const attr of this.attrs) {
            const render_val = attr.v.render_val();
            if (render_val) {
                element.setAttribute(attr.k, render_val);
            }
        }
        if (this.pink) {
            element.style.backgroundColor = "pink";
        }
        return element;
    }

    as_raw_html(): string {
        return as_raw_html(this.to_dom());
    }
}

class ParenthesizedTag {
    tag: Tag;

    constructor(tag: Tag) {
        this.tag = tag;
    }

    to_source(indent: string): string {
        return indent + `(${this.tag.to_source("")})`;
    }

    to_dom(): DocumentFragment {
        const frag = document.createDocumentFragment();
        frag.append(document.createTextNode("("));
        frag.append(this.tag.to_dom());
        frag.append(document.createTextNode(")"));
        return frag;
    }

    as_raw_html(): string {
        return as_raw_html(this.to_dom());
    }
}

export function icon_button({
    button_classes,
    icon_classes,
}: {
    button_classes: ClassString[];
    icon_classes: ClassString[];
}): Tag {
    return button_tag({
        classes: button_classes,
        children: [
            i_tag({
                classes: icon_classes,
            }),
        ],
    });
}

// Add a new function wrapper to create an object instead of
// using the class constructor in a caller outside this module.
export function i_tag(tag_spec: TagSpec): Tag {
    return new Tag("i", tag_spec);
}

export function ul_tag(tag_spec: TagSpec): Tag {
    return new Tag("ul", tag_spec);
}

export function h5_tag(tag_spec: TagSpec): Tag {
    return new Tag("h5", tag_spec);
}

export function h4_tag(tag_spec: TagSpec): Tag {
    return new Tag("h4", tag_spec);
}

export function span_tag(tag_spec: TagSpec): Tag {
    return new Tag("span", tag_spec);
}

export function a_tag(tag_spec: TagSpec): Tag {
    return new Tag("a", tag_spec);
}

export function li_tag(tag_spec: TagSpec): Tag {
    return new Tag("li", tag_spec);
}

export function button_tag(tag_spec: TagSpec): Tag {
    return new Tag("button", tag_spec);
}

export function div_tag(tag_spec: TagSpec): Tag {
    return new Tag("div", tag_spec);
}

export function img_tag(tag_spec: TagSpec): Tag {
    return new Tag("img", tag_spec);
}

export function input_text_tag(info: {
    classes: ClassString[];
    attrs?: Attr[];
    placeholder_value: TranslatedAttrValue;
    pink?: boolean;
}): InputTextTag {
    return new InputTextTag(info);
}

export function trusted_simple_string(str: string): TrustedSimpleString {
    return new TrustedSimpleString(str);
}

export function bool_var(info: BoolVarSpec): BoolVar {
    return new BoolVar(info);
}

export function trusted_if_else_string(info: TrustedIfElseStringSpec): TrustedIfElseString {
    return new TrustedIfElseString(info);
}

export function trusted_if_string(info: TrustedConditionalStringSpec): TrustedIfString {
    return new TrustedIfString(info);
}

export function trusted_unless_string(info: TrustedConditionalStringSpec): TrustedUnlessString {
    return new TrustedUnlessString(info);
}

export function attr(k: string, v: TrustedString | TranslatedAttrValue): Attr {
    return new Attr(k, v);
}

export function translated_attr_value(info: TranslatedAttrValueSpec): TranslatedAttrValue {
    return new TranslatedAttrValue(info);
}

export function block(info: BlockSpec): Block {
    return new Block(info);
}

export function text_var(info: TextVarSpec): TextVar {
    return new TextVar(info);
}

export function unescaped_text_string(str: string): UnEscapedTextString {
    return new UnEscapedTextString(str);
}

export function unescaped_attr_string(str: string): UnEscapedAttrString {
    return new UnEscapedAttrString(str);
}

export function parenthesized_tag(tag: Tag): ParenthesizedTag {
    return new ParenthesizedTag(tag);
}

export function translated_text(info: TranslatedTextSpec): TranslatedText {
    return new TranslatedText(info);
}

export function trusted_attr_string_var(info: TrustedAttrStringVarSpec): TrustedAttrStringVar {
    return new TrustedAttrStringVar(info);
}

export function comment(str: string): Comment {
    return new Comment(str);
}

export function simple_each(info: SimpleEachSpec): SimpleEach {
    return new SimpleEach(info);
}

export function trusted_html(html: string): TrustedHtml {
    return new TrustedHtml(html);
}

export function partial(info: PartialSpec): Partial {
    return new Partial(info);
}

export function trusted_class_with_var_suffix(
    info: TrustedClassWithVarSuffixSpec,
): TrustedClassWithVarSuffix {
    return new TrustedClassWithVarSuffix(info);
}
