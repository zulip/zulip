import _ from "lodash";
import assert from "minimalistic-assert";

// How to determine the direction of a paragraph (P1-P3): https://www.unicode.org/reports/tr9/tr9-35.html#The_Paragraph_Level
// Embedding level: https://www.unicode.org/reports/tr9/tr9-35.html#BD2
// How to find the matching PDI for an isolation initiator: https://www.unicode.org/reports/tr9/tr9-35.html#BD9
// Bidirectional character types: https://www.unicode.org/reports/tr9/tr9-35.html#Table_Bidirectional_Character_Types

// Ranges data is extracted from: https://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedBidiClass.txt
// References:
// https://www.unicode.org/reports/tr44/tr44-18.html#UnicodeData.txt
// https://www.unicode.org/reports/tr44/tr44-18.html#Extracted_Properties_Table
// https://www.unicode.org/Public/9.0.0/ucd/UnicodeData.txt
// https://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedBidiClass.txt

/**
 * Splits {@link raw} into parts of length {@link part_length},
 * and then converts each part to a character using simple base
 * conversion with the digits {@link digits}.
 * @param {string} digits
 * @param {number} part_length
 * @param {string} raw
 * @returns {number[]}
 */
function convert_from_raw(digits: string, part_length: number, raw: string): number[] {
    const result = [];
    for (let i = 0; i < raw.length; ) {
        let t = 0;
        for (let j = 0; j < part_length; j += 1) {
            t = t * digits.length + digits.indexOf(raw.charAt(i));
            i += 1;
        }
        result.push(t);
    }
    return result;
}

/** Isolate initiator characters. */
const i_chars = new Set([0x2066, 0x2067, 0x2068]);
/** Pop directional isolate character. */
const pdi_chars = new Set([0x2069]);
/** The digits that are used for base conversions from base 92. */
const digits =
    '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&()*+,-./:;<=>?@[]^_`{|}~';
/**
 * Ranges of strong non-left-to-right characters (right-to-left, and arabic-letter).
 *
 * The ranges are stored as pairs of characters, the first
 * character of the range, and the last character of the range.
 * All ranges are concatenated together and stored here.
 */
const rl_ranges = [
    ...convert_from_raw(
        digits,
        2,
        'fIfIf}f}g0g0g3g3g6g6g8g"g,g,g/g/g;g;g~hKh?h[h^j1jhjijqjrjCjYj!j~krlplBm2mcmdmimJmOmOmYmYm#m#m*nknooP|j|j',
    ),
    ...convert_from_raw(
        digits,
        3,
        '7S)7S)7S+7S>7S@7YZ7Y#7!n7!U7!(7!*7!+7#07$O7}U81%81(84g84k84k84n84r84w84+84/84<84>86Y86"87Q87Y8gv8g"8k=e)]e,fe,ne-De-Le|je|mf0f',
    ),
];
/**
 * Ranges of strong left-to-right characters.
 *
 * The ranges are stored as pairs of characters, the first
 * character of the range, and the last character of the range.
 * All ranges are concatenated together and stored here.
 */
const lr_ranges = [
    ...convert_from_raw(
        digits,
        2,
        '0$0}151u1<1<1|1|2222282u2w2!2#7Q7T7Z7:7;80848e8e9Q9T9W9$9&9+9.9.9:b1b3cOcWfBfDfEp7pZp"p"p$p(p;p>p@p]q0q9qcqEqGr7r9rcrhrorqrJrMrZr#r*r,r:r=sHsJsMsPsSsVsWs!s#s%t3t6t8tatktnt=t?t]t}t}u1u4u6upusuEuGuUuWvnvpvqvsvsvxvEvGvNvPvZv#w1w3w"w$w:w<xmxvxzxBy5y9ydyhyhymysyvyFyIy"y+y,y.zDzFzTzWz;z>AgAiA>A^B0B2BlBoCxCzCFCJCJCLDIDKDLDTDWDYD%D/E>E@E[E}E}F1FbFiF~G2GsGuGuGwGwGCG{HbHbHhHhHkHoHAHAH-H?H[J0J5J5JcJcJfJgJjJHJKJNJRJ(J-J^J`J{J~K4K6KkKmR>R]SDSOTXTZ!T!V!@!^#h#l#N#R#?#]$l$o$`$}$}%6%d%f%g%s%y%A%A%C%T%%%+%`(k(n(U(W)[)`)}*1*9*b*g*k*n*p*r*u+|,w,S,V,W,Y-p-r-r-z-z-B-B-D-E-N-S-$-%-(.n.D/b/g/"/$/$/+/+/-/;/=:q:A:L:O:?:_:`:}:};2;V;X;X;!;#;%;%;*<z<I<J<M>f>j>j>x>x>F>I>K>P>R>T>W@+[y[C[I{s{u{u{y{I{M{Y{#{:{>|0|3|3|i|i}p}r}D}D}T}+~Z~/~<~<~[~[',
    ),
    ...convert_from_raw(
        digits,
        3,
        '0~_10310510510910d10k10k10m10m10o10o10q10t10v10F10I10L10R10V10!10"10>11s11w11z15}16%17117118f18f18T18=18~19j19>1a$1fU1fU1js1m71s]1s^1tq1tr1t!1t#1t;1t;1t_1uj1uo1w]1w~1x21x61xc1xk1yS1yU1zX1A)1Bz1B!1B!1CY1C+1Fa1Fz1FM1FP1FV1FX1F^1G11G61G71G91Gd1Gg1Gk1Go1Hk1Hp1Hr1Ht1Iq1Is1KD1K:1LE1LH1L~1Mg1MH1ML1N41Nk1Nv1NA1Pi1Pn1Qt1Qw1Q!1Q#2wv2x44|[4}L52452853a53s53V53Y54L54O54"55656f56h57J57L57N57P57S57U57>57[57[57{58758a58&58,59T59W59[5aa5aZ5a*5b25be5bX5b"5ci5ck5cl5cq5cr5ct5c(5c*5dI5dP5dQ5dT5dU5dX5d*5d,5d=5d?5ez5eB5e`5e|5e|5f15f25f55f95fc5fc5fe5fT5fW5f$5f&5is5iu5iv5ix5iA5iC7S(7"67"b7""7""7"[7"[7"{7"~7$Q7$Q7$^7%i7%p7%O7%!7&~7(77(77(f7(f7(w7+c7+e7+/7,Z7,"7,:7,=7,?7->7-@7:v7:Y7;|7<37}T8k>8k>8k@8lH8lX8l)8l}8mm8mq8m.8m=8m>8m[8nX8n"8o68oc8oc8ol8o@8o]8p38p68pV8p&8p;8p?8q_8q}8q~8r18r18r48r98rb8s<8s>8s@8s~8tj8tm8t=8t?8t[8t^8ut8uB8uD8uJ8wT8w#8w$8w)8w)8w+8x_8y18y18y38y68y98y98yc8A$8A*8A/8A<8A<8A?8Bf8Bi8Ca8Cj8Ck8Cm8Cm8Cp8CT8C)8DC8DE8DE8DG8DH8DO8DO8DQ8EY8E#8E$8E*8E*8E:8S+8S=8S=8S_8T;8U88U98Uh8Uh8Uk8Uk8Una|[a||a}Ta}"ba*ba/dFgdFjdFjdFoe72e76e7ee7ve7we7Ee7)e7.e8"e9GebHecDemiemkem:em<enGenIeo8eoaeo%eo(eo;epAeu`evPevSewdewkewmewzewBewWew#ew#ew>eLXeL&eL&eL^eL_eM2eM2eM5eM5eMbe)[f0Yf0"f1,f1[f27f28f2of2of2Ef2Ef2<f2`f39f49f4cf8LfjffjrfjFfjHfjPfjXfk]fl3fl|fmDfmQfmTfnkfnrfnCfnHfn]fn~foufpzfpPfpPfpYfp&fp)fp*fp[fp[fq4fq7fqnfqTfq.frrfrtfIZfI#nl1nl4u|xu|AC$$C$(KG5KG8SiBSiEZ_)Z_,)"9)"c;DF;DI^f-',
    ),
    ...convert_from_raw(digits, 4, "0^f:10]d10]g18YJ18YM1gA;1g?A1odh1odk1v?N1v?Q1DV?1DV]1DV]"),
];

/**
 * Gets a character and returns a simplified version of its bidirectional class.
 * @param {number} ch A character to get its bidirectional class.
 * @returns {'I' | 'PDI' | 'R' | 'L' | 'Other'}
 */
function get_bidi_class(ch: number): "I" | "PDI" | "R" | "L" | "Other" {
    if (i_chars.has(ch)) {
        return "I"; // LRI, RLI, FSI
    }
    if (pdi_chars.has(ch)) {
        return "PDI";
    }
    let i = _.sortedIndex(rl_ranges, ch);
    if (i < rl_ranges.length && (rl_ranges[i] === ch || i % 2 === 1)) {
        return "R"; // R, AL
    }
    i = _.sortedIndex(lr_ranges, ch);
    if (i < lr_ranges.length && (lr_ranges[i] === ch || i % 2 === 1)) {
        return "L";
    }
    return "Other";
}

/**
 * Gets the direction that should be used to show the string.
 * @param {string} str The string to get its direction.
 * @returns {'ltr' | 'rtl'}
 */
export function get_direction(str: string): "ltr" | "rtl" {
    let isolations = 0;
    for (const ch of str) {
        const bidi_class = get_bidi_class(ch.codePointAt(0)!);
        switch (bidi_class) {
            case "I":
                // LRI, RLI, FSI
                isolations += 1;
                break;
            case "PDI":
                if (isolations > 0) {
                    isolations -= 1;
                }
                break;
            case "R":
                // R, AL
                if (isolations === 0) {
                    return "rtl";
                }
                break;
            case "L":
                if (isolations === 0) {
                    return "ltr";
                }
                break;
        }
    }
    return "ltr";
}

export function set_rtl_class_for_textarea($textarea: JQuery<HTMLTextAreaElement>): void {
    // Set the rtl class if the text has an rtl direction, remove it otherwise
    let text = $textarea.val();
    assert(typeof text === "string", "Passed HTML element must be a textarea.");
    if (text.startsWith("```quote")) {
        text = text.slice(8);
    }
    if (get_direction(text) === "rtl") {
        $textarea.addClass("rtl");
    } else {
        $textarea.removeClass("rtl");
    }
}
