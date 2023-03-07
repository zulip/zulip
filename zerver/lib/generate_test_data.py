import itertools
import os
import random
from typing import Any, Dict, List

import orjson

from scripts.lib.zulip_tools import get_or_create_dev_uuid_var_path
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX


def load_config() -> Dict[str, Any]:
    with open("zerver/tests/fixtures/config.generate_data.json", "rb") as infile:
        config = orjson.loads(infile.read())

    return config


def generate_topics(num_topics: int) -> List[str]:
    config = load_config()["gen_fodder"]

    topics = []
    # Make single word topics account for 30% of total topics.
    # Single word topics are most common, thus
    # it is important we test on it.
    num_single_word_topics = num_topics // 3
    for _ in itertools.repeat(None, num_single_word_topics):
        topics.append(random.choice(config["nouns"]))

    sentence = ["adjectives", "nouns", "connectors", "verbs", "adverbs"]
    for pos in sentence:
        # Add an empty string so that we can generate variable length topics.
        config[pos].append("")

    for _ in itertools.repeat(None, num_topics - num_single_word_topics):
        generated_topic = [random.choice(config[pos]) for pos in sentence]
        topic = " ".join(filter(None, generated_topic))
        topics.append(topic)

    # Mark a small subset of topics as resolved in some streams, and
    # many topics in a few streams. Note that these don't have the
    # "Marked as resolved" messages, so don't match the normal user
    # experience perfectly.
    if random.random() < 0.15:
        resolved_topic_probability = 0.5
    else:
        resolved_topic_probability = 0.05

    final_topics = []
    for topic in topics:
        if random.random() < resolved_topic_probability:
            final_topics.append(RESOLVED_TOPIC_PREFIX + topic)
        else:
            final_topics.append(topic)

    return final_topics


def load_generators(config: Dict[str, Any]) -> Dict[str, Any]:
    results = {}
    cfg = config["gen_fodder"]

    results["nouns"] = itertools.cycle(cfg["nouns"])
    results["adjectives"] = itertools.cycle(cfg["adjectives"])
    results["connectors"] = itertools.cycle(cfg["connectors"])
    results["verbs"] = itertools.cycle(cfg["verbs"])
    results["adverbs"] = itertools.cycle(cfg["adverbs"])
    results["emojis"] = itertools.cycle(cfg["emoji"])
    results["links"] = itertools.cycle(cfg["links"])

    results["maths"] = itertools.cycle(cfg["maths"])
    results["inline-code"] = itertools.cycle(cfg["inline-code"])
    results["code-blocks"] = itertools.cycle(cfg["code-blocks"])
    results["quote-blocks"] = itertools.cycle(cfg["quote-blocks"])
    results["images"] = itertools.cycle(cfg["images"])

    results["lists"] = itertools.cycle(cfg["lists"])

    return results


def parse_file(config: Dict[str, Any], gens: Dict[str, Any], corpus_file: str) -> List[str]:
    # First, load the entire file into a dictionary,
    # then apply our custom filters to it as needed.

    paragraphs: List[str] = []

    with open(corpus_file) as infile:
        # OUR DATA: we need to separate the person talking and what they say
        paragraphs = remove_line_breaks(infile)
        paragraphs = add_flair(paragraphs, gens)

    return paragraphs


def get_flair_gen(length: int) -> List[str]:
    # Grab the percentages from the config file
    # create a list that we can consume that will guarantee the distribution
    result = []

    for k, v in config["dist_percentages"].items():
        result.extend([k] * int(v * length / 100))

    result.extend(["None"] * (length - len(result)))

    random.shuffle(result)
    return result


def add_flair(paragraphs: List[str], gens: Dict[str, Any]) -> List[str]:
    # roll the dice and see what kind of flair we should add, if any
    results = []

    flair = get_flair_gen(len(paragraphs))

    for i in range(len(paragraphs)):
        key = flair[i]
        if key == "None":
            txt = paragraphs[i]
        elif key == "italic":
            txt = add_md("*", paragraphs[i])
        elif key == "bold":
            txt = add_md("**", paragraphs[i])
        elif key == "strike-thru":
            txt = add_md("~~", paragraphs[i])
        elif key == "quoted":
            txt = ">" + paragraphs[i]
        elif key == "quote-block":
            txt = paragraphs[i] + "\n" + next(gens["quote-blocks"])
        elif key == "inline-code":
            txt = paragraphs[i] + "\n" + next(gens["inline-code"])
        elif key == "code-block":
            txt = paragraphs[i] + "\n" + next(gens["code-blocks"])
        elif key == "math":
            txt = paragraphs[i] + "\n" + next(gens["maths"])
        elif key == "list":
            txt = paragraphs[i] + "\n" + next(gens["lists"])
        elif key == "emoji":
            txt = add_emoji(paragraphs[i], next(gens["emojis"]))
        elif key == "link":
            txt = add_link(paragraphs[i], next(gens["links"]))
        elif key == "images":
            # Ideally, this would actually be a 2-step process that
            # first hits the `upload` endpoint and then adds that URL;
            # this is the hacky version where we just use inline image
            # previews of files already in the project (which are the
            # only files we can link to as being definitely available
            # even when developing offline).
            txt = paragraphs[i] + "\n" + next(gens["images"])

        results.append(txt)

    return results


def add_md(mode: str, text: str) -> str:
    # mode means: bold, italic, etc.
    # to add a list at the end of a paragraph, * item one\n * item two

    # find out how long the line is, then insert the mode before the end

    vals = text.split()
    start = random.randrange(len(vals))
    end = random.randrange(len(vals) - start) + start
    vals[start] = mode + vals[start]
    vals[end] = vals[end] + mode

    return " ".join(vals).strip()


def add_emoji(text: str, emoji: str) -> str:
    vals = text.split()
    start = random.randrange(len(vals))

    vals[start] = vals[start] + " " + emoji + " "
    return " ".join(vals)


def add_link(text: str, link: str) -> str:
    vals = text.split()
    start = random.randrange(len(vals))

    vals[start] = vals[start] + " " + link + " "

    return " ".join(vals)


def remove_line_breaks(fh: Any) -> List[str]:
    # We're going to remove line breaks from paragraphs
    results = []  # save the dialogs as tuples with (author, dialog)

    para = []  # we'll store the lines here to form a paragraph

    for line in fh:
        text = line.strip()
        if text != "":
            para.append(text)
        else:
            if para:
                results.append(" ".join(para))
            # reset the paragraph
            para = []
    if para:
        results.append(" ".join(para))

    return results


def write_file(paragraphs: List[str], filename: str) -> None:
    with open(filename, "wb") as outfile:
        outfile.write(orjson.dumps(paragraphs))


def create_test_data() -> None:
    gens = load_generators(config)  # returns a dictionary of generators

    paragraphs = parse_file(config, gens, config["corpus"]["filename"])

    write_file(
        paragraphs,
        os.path.join(get_or_create_dev_uuid_var_path("test-backend"), "test_messages.json"),
    )


config = load_config()

if __name__ == "__main__":
    create_test_data()
