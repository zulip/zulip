import _ from 'underscore';
import { Message, Subscription } from './data_structures';

export function get_hash_category(hash: string): string {
    // given "#streams/subscribed", returns "streams"
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
}

export function get_hash_section(hash: string): string {
    // given "#settings/your-account", returns "your-account"
    // given '#streams/5/social", returns "5"
    if (!hash) {
        return '';
    }

    var parts = hash.replace(/\/$/, "").split(/\//);

    return parts[1] || '';
}

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
export function encodeHashComponent(str: string): string {
    return encodeURIComponent(str)
        .replace(/\./g, '%2E')
        .replace(/%/g, '.');
}

export function encode_operand(operator: string, operand: string): string {
    if (operator === 'group-pm-with' || operator === 'pm-with' || operator === 'sender') {
        var slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    if (operator === 'stream') {
        return encode_stream_name(operand);
    }

    return encodeHashComponent(operand);
}

export function encode_stream_id(stream_id: number): string {
    // stream_data appends the stream name, but it does not do the
    // URI encoding piece
    var slug = stream_data.id_to_slug(stream_id);

    return encodeHashComponent(slug);
}

export function encode_stream_name(operand: string): string {
    // stream_data prefixes the stream id, but it does not do the
    // URI encoding piece
    operand = stream_data.name_to_slug(operand);

    return encodeHashComponent(operand);
}

export function decodeHashComponent(str: string): string {
    return decodeURIComponent(str.replace(/\./g, '%'));
}

export function decode_operand(operator: string, operand: string): string {
    if (operator === 'group-pm-with' || operator === 'pm-with' || operator === 'sender') {
        var emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    operand = decodeHashComponent(operand);

    if (operator === 'stream') {
        return stream_data.slug_to_name(operand);
    }

    return operand;
}

export function by_stream_uri(stream_id: number): string {
    return "#narrow/stream/" + encode_stream_id(stream_id);
}

export function by_stream_topic_uri(stream_id: number, topic: string): string {
    return "#narrow/stream/" + encode_stream_id(stream_id) +
           "/topic/" + encodeHashComponent(topic);
}

type NarrowOperator = {
    negated?: boolean;
    operator: string;
    operand: string;
};

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
export function operators_to_hash(operators: NarrowOperator[] | undefined): string {
    var hash = '#';

    if (operators !== undefined) {
        hash = '#narrow';
        _.each(operators, function (elem) {
            // Support legacy tuples.
            var operator = elem.operator;
            var operand = elem.operand;

            var sign = elem.negated ? '-' : '';
            hash += '/' + sign + encodeHashComponent(operator)
                  + '/' + encode_operand(operator, operand);
        });
    }

    return hash;
}

export function by_sender_uri(reply_to: string): string {
    return operators_to_hash([
        {operator: 'sender', operand: reply_to},
    ]);
}

export function pm_with_uri(reply_to: string): string {
    return operators_to_hash([
        {operator: 'pm-with', operand: reply_to},
    ]);
}

export function huddle_with_uri(user_ids_string: string): string {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/pm-with/" + user_ids_string + '-group';
}

export function by_conversation_and_time_uri(message: Message): string {
    var absolute_url = window.location.protocol + "//" +
        window.location.host + "/" +
        window.location.pathname.split('/')[1];

    var suffix = "/near/" + encodeHashComponent(message.id.toString());

    if (message.type === "stream") {
        return absolute_url +
            by_stream_topic_uri(message.stream_id, util.get_message_topic(message)) +
            suffix;
    }

    return absolute_url + people.pm_perma_link(message) + suffix;
}

export function stream_edit_uri(sub: Subscription): string {
    var hash = "#streams" + "/" + sub.stream_id + "/" + encodeHashComponent(sub.name);
    return hash;
}

export function parse_narrow(hash: string[]): NarrowOperator[] | undefined {
    var i;
    var operators = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        var operator = decodeHashComponent(hash[i]);
        // Do not parse further if empty operator encountered.
        if (operator === '') {
            break;
        }

        var raw_operand = hash[i + 1];

        if (!raw_operand) {
            return undefined;
        }

        var operand  = decode_operand(operator, raw_operand);
        var negated = false;
        if (operator[0] === '-') {
            negated = true;
            operator = operator.slice(1);
        }
        operators.push({negated: negated, operator: operator, operand: operand});
    }
    return operators;
}
