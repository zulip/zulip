var rtl = (function () {

var exports = {};

// How to determine the direction of a paragraph (P1-P3): http://www.unicode.org/reports/tr9/tr9-35.html#The_Paragraph_Level
// Embedding level: http://www.unicode.org/reports/tr9/tr9-35.html#BD2
// How to find the matching PDI for an isolation initiator: http://www.unicode.org/reports/tr9/tr9-35.html#BD9
// Bidirectional character types: http://www.unicode.org/reports/tr9/tr9-35.html#Table_Bidirectional_Character_Types

// Ranges data is extracted from: http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedBidiClass.txt
// References:
// http://www.unicode.org/reports/tr44/tr44-18.html#UnicodeData.txt
// http://www.unicode.org/reports/tr44/tr44-18.html#Extracted_Properties_Table
// http://www.unicode.org/Public/9.0.0/ucd/UnicodeData.txt
// http://www.unicode.org/Public/9.0.0/ucd/extracted/DerivedBidiClass.txt


/**
 * Splits {@link raw} into parts of length {@link part_length},
 * and then converts each part to a character using simple base
 * conversion with the digits {@link digits}.
 * @param {string} digits
 * @param {number} part_length
 * @param {string} raw
 * @returns {string}
 */
function convert_from_raw(digits, part_length, raw) {
    var result = '';
    for (var i = 0; i < raw.length;) {
        var t = 0;
        for (var j = 0; j < part_length; j += 1) {
            t = t * digits.length + digits.indexOf(raw.charAt(i));
            i += 1;
        }
        result += String.fromCharCode(t);
    }
    return result;
}

/** Isolate initiator characters. */
var i_chars = '\u2066\u2067\u2068';
/** Pop directional isolate character. */
var pdi_chars = '\u2069';
/** The digits that are used for base conversions from base 92. */
var digits = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&()*+,-./:;<=>?@[]^_`{|}~';
/**
 * Ranges of strong non-left-to-right characters (right-to-left, and arabic-letter).
 *
 * The ranges are stored as pairs of characters, the first
 * character of the range, and the last character of the range.
 * All ranges are concatenated together and stored here.
 */
var rl_ranges = convert_from_raw(digits, 3, '0fI0fI0f}0f}0g00g00g30g30g60g60g80g"0g,0g,0g/0g/0g;0g;0g~0hK0h?0h[0h^0j10jh0ji0jq0jr0jC0jY0j!0j~0kr0lp0lB0m20mc0md0mi0mJ0mO0mO0mY0mY0m#0m#0m*0nk0no0oP0|j0|j7S)7S)7S+7S>7S@7YZ7Y#7!n7!U7!(7!*7!+7#07$O7}U81%81(84g84k84k84n84r84w84+84/84<84>86Y86"87Q87Y8gv8g"8k=e)]e,fe,ne-De-Le|je|mf0f');
/**
 * Ranges of strong left-to-right characters.
 *
 * The ranges are stored as pairs of characters, the first
 * character of the range, and the last character of the range.
 * All ranges are concatenated together and stored here.
 */
var lr_ranges = convert_from_raw(digits, 3, '00$00}01501u01<01<01|01|02202202802u02w02!02#07Q07T07Z07:07;08008408e08e09Q09T09W09$09&09+09.09.09:0b10b30cO0cW0fB0fD0fE0p70pZ0p"0p"0p$0p(0p;0p>0p@0p]0q00q90qc0qE0qG0r70r90rc0rh0ro0rq0rJ0rM0rZ0r#0r*0r,0r:0r=0sH0sJ0sM0sP0sS0sV0sW0s!0s#0s%0t30t60t80ta0tk0tn0t=0t?0t]0t}0t}0u10u40u60up0us0uE0uG0uU0uW0vn0vp0vq0vs0vs0vx0vE0vG0vN0vP0vZ0v#0w10w30w"0w$0w:0w<0xm0xv0xz0xB0y50y90yd0yh0yh0ym0ys0yv0yF0yI0y"0y+0y,0y.0zD0zF0zT0zW0z;0z>0Ag0Ai0A>0A^0B00B20Bl0Bo0Cx0Cz0CF0CJ0CJ0CL0DI0DK0DL0DT0DW0DY0D%0D/0E>0E@0E[0E}0E}0F10Fb0Fi0F~0G20Gs0Gu0Gu0Gw0Gw0GC0G{0Hb0Hb0Hh0Hh0Hk0Ho0HA0HA0H-0H?0H[0J00J50J50Jc0Jc0Jf0Jg0Jj0JH0JK0JN0JR0J(0J-0J^0J`0J{0J~0K40K60Kk0Km0R>0R]0SD0SO0TX0TZ0!T0!V0!@0!^0#h0#l0#N0#R0#?0#]0$l0$o0$`0$}0$}0%60%d0%f0%g0%s0%y0%A0%A0%C0%T0%%0%+0%`0(k0(n0(U0(W0)[0)`0)}0*10*90*b0*g0*k0*n0*p0*r0*u0+|0,w0,S0,V0,W0,Y0-p0-r0-r0-z0-z0-B0-B0-D0-E0-N0-S0-$0-%0-(0.n0.D0/b0/g0/"0/$0/$0/+0/+0/-0/;0/=0:q0:A0:L0:O0:?0:_0:`0:}0:}0;20;V0;X0;X0;!0;#0;%0;%0;*0<z0<I0<J0<M0>f0>j0>j0>x0>x0>F0>I0>K0>P0>R0>T0>W0@+0[y0[C0[I0{s0{u0{u0{y0{I0{M0{Y0{#0{:0{>0|00|30|30|i0|i0}p0}r0}D0}D0}T0}+0~Z0~/0~<0~<0~[0~[0~_10310510510910d10k10k10m10m10o10o10q10t10v10F10I10L10R10V10!10"10>11s11w11z15}16%17117118f18f18T18=18~19j19>1a$1fU1fU1js1m71s]1s^1tq1tr1t!1t#1t;1t;1t_1uj1uo1w]1w~1x21x61xc1xk1yS1yU1zX1A)1Bz1B!1B!1CY1C+1Fa1Fz1FM1FP1FV1FX1F^1G11G61G71G91Gd1Gg1Gk1Go1Hk1Hp1Hr1Ht1Iq1Is1KD1K:1LE1LH1L~1Mg1MH1ML1N41Nk1Nv1NA1Pi1Pn1Qt1Qw1Q!1Q#2wv2x44|[4}L52452853a53s53V53Y54L54O54"55656f56h57J57L57N57P57S57U57>57[57[57{58758a58&58,59T59W59[5aa5aZ5a*5b25be5bX5b"5ci5ck5cl5cq5cr5ct5c(5c*5dI5dP5dQ5dT5dU5dX5d*5d,5d=5d?5ez5eB5e`5e|5e|5f15f25f55f95fc5fc5fe5fT5fW5f$5f&5is5iu5iv5ix5iA5iC7S(7"67"b7""7""7"[7"[7"{7"~7$Q7$Q7$^7%i7%p7%O7%!7&~7(77(77(f7(f7(w7+c7+e7+/7,Z7,"7,:7,=7,?7->7-@7:v7:Y7;|7<37}T8k>8k>8k@8lH8lX8l)8l}8mm8mq8m.8m=8m>8m[8nX8n"8o68oc8oc8ol8o@8o]8p38p68pV8p&8p;8p?8q_8q}8q~8r18r18r48r98rb8s<8s>8s@8s~8tj8tm8t=8t?8t[8t^8ut8uB8uD8uJ8wT8w#8w$8w)8w)8w+8x_8y18y18y38y68y98y98yc8A$8A*8A/8A<8A<8A?8Bf8Bi8Ca8Cj8Ck8Cm8Cm8Cp8CT8C)8DC8DE8DE8DG8DH8DO8DO8DQ8EY8E#8E$8E*8E*8E:8S+8S=8S=8S_8T;8U88U98Uh8Uh8Uk8Uk8Una|[a||a}Ta}"ba*ba/dFgdFjdFjdFoe72e76e7ee7ve7we7Ee7)e7.e8"e9GebHecDemiemkem:em<enGenIeo8eoaeo%eo(eo;epAeu`evPevSewdewkewmewzewBewWew#ew#ew>eLXeL&eL&eL^eL_eM2eM2eM5eM5eMbe)[f0Yf0"f1,f1[f27f28f2of2of2Ef2Ef2<f2`f39f49f4cf8LfjffjrfjFfjHfjPfjXfk]fl3fl|fmDfmQfmTfnkfnrfnCfnHfn]fn~foufpzfpPfpPfpYfp&fp)fp*fp[fp[fq4fq7fqnfqTfq.frrfrtfIZfI#nl1nl4u|xu|AC$$C$(KG5KG8SiBSiEZ_)Z_,)"9)"c;DF;DI^f-^f:10]d10]g18YJ18YM1gA;1g?A1odh1odk1v?N1v?Q1DV?1DV]1DV]');

/**
 * Gets a character and returns a simplified version of its bidirectional class.
 * @param {string} ch A character to get its bidirectional class.
 * @returns {'I' | 'PDI' | 'R' | 'L' | 'Other'}
 */
function get_bidi_class(ch) {
    if (i_chars.indexOf(ch) !== -1) {
        return 'I'; // LRI, RLI, FSI
    }
    if (pdi_chars.indexOf(ch) !== -1) {
        return 'PDI';
    }
    var i = util.lower_bound(rl_ranges, ch);
    if (i < rl_ranges.length && (rl_ranges[i] === ch || i % 2 === 1)) {
        return 'R'; // R, AL
    }
    i = util.lower_bound(lr_ranges, ch);
    if (i < lr_ranges.length && (lr_ranges[i] === ch || i % 2 === 1)) {
        return 'L';
    }
    return 'Other';
}

/**
 * Gets the direction that should be used to show the string.
 * @param {string} str The string to get its direction.
 * @returns {'ltr' | 'rtl'}
 */
exports.get_direction = function (str) {
    var isolations = 0;
    for (var i = 0; i < str.length; i += 1) {
        var bidi_class = get_bidi_class(str.charAt(i));
        if (bidi_class === 'I') { // LRI, RLI, FSI
            isolations += 1;
        } else if (bidi_class === 'PDI') {
            if (isolations > 0) {
                isolations -= 1;
            }
        } else if (bidi_class === 'R') { // R, AL
            if (isolations === 0) {
                return 'rtl';
            }
        } else if (bidi_class === 'L') {
            if (isolations === 0) {
                return 'ltr';
            }
        }
    }
    return 'ltr';
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = rtl;
}
