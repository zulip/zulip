import * as h from "./html.ts";

type BoolVar = h.BoolVar;
type Block = h.Block;

type ConditionalBlockSpec = {bool: BoolVar; block: Block; source_format?: h.SourceFormat};

class IfBlock implements h.CustomElement {
    block: Block;
    bool: BoolVar;
    source_format: h.SourceFormat;

    constructor(info: ConditionalBlockSpec) {
        this.bool = info.bool;
        this.block = info.block;
        this.source_format = info.source_format ?? "inline";
    }

    to_source(indent: string): string {
        return h.format_block({
            source_format: this.source_format,
            indent,
            start_tag: `{{#if ${this.bool.to_source()}}}`,
            end_tag: "{{/if}}",
            children: this.block.elements,
        });
    }

    to_dom(): Node {
        if (this.bool.b) {
            return this.block.to_dom();
        }
        return document.createDocumentFragment();
    }
}

class UnlessBlock implements h.CustomElement {
    block: Block;
    bool: BoolVar;
    source_format: h.SourceFormat;

    constructor(info: ConditionalBlockSpec) {
        this.block = info.block;
        this.bool = info.bool;
        this.source_format = info.source_format ?? "inline";
    }

    to_source(indent: string): string {
        return h.format_block({
            source_format: this.source_format,
            indent,
            start_tag: `{{#unless ${this.bool.to_source()}}}`,
            end_tag: "{{/unless}}",
            children: this.block.elements,
        });
    }

    to_dom(): Node {
        if (!this.bool.b) {
            return this.block.to_dom();
        }
        return document.createDocumentFragment();
    }
}

type IfElseIfElseBlockSpec = {
    if_info: ConditionalBlockSpec;
    else_if_info: ConditionalBlockSpec;
    else_block: Block;
};

export class IfElseIfElseBlock implements h.CustomElement {
    if_bool: BoolVar;
    else_if_bool: BoolVar;

    if_block: Block;
    else_if_block: Block;
    else_block: Block;

    constructor(info: IfElseIfElseBlockSpec) {
        const {if_info, else_if_info, else_block} = info;
        this.if_bool = if_info.bool;
        this.if_block = if_info.block;
        this.else_if_bool = else_if_info.bool;
        this.else_if_block = else_if_info.block;
        this.else_block = else_block;
    }

    to_source(indent: string): string {
        return (
            indent +
            `{{#if ${this.if_bool.to_source()}}}\n` +
            this.if_block.to_source(indent + "    ") +
            indent +
            `{{else if ${this.else_if_bool.to_source()}}}\n` +
            this.else_if_block.to_source(indent + "    ") +
            indent +
            `{{else}}\n` +
            this.else_block.to_source(indent + "    ") +
            indent +
            "{{/if}}"
        );
    }

    to_dom(): Node {
        if (this.if_bool.b) {
            return this.if_block.to_dom();
        } else if (this.else_if_bool.b) {
            return this.else_if_block.to_dom();
        }
        return this.else_block.to_dom();
    }
}

export function if_bool_then_block(info: ConditionalBlockSpec): IfBlock {
    return new IfBlock(info);
}

export function unless_bool_then_block(info: ConditionalBlockSpec): UnlessBlock {
    return new UnlessBlock(info);
}

export function if_bool_then_x_else_if_bool_then_y_else_z(
    info: IfElseIfElseBlockSpec,
): IfElseIfElseBlock {
    return new IfElseIfElseBlock(info);
}
