import itertools
import ujson
import random
from typing import List, Dict, Any, Text, Optional

def load_config() -> Dict[str, Any]:
    with open("zerver/fixtures/config.generate_data.json", "r") as infile:
        config = ujson.load(infile)

    return config

def get_stream_title(gens: Dict[str, Any]) -> str:

    return next(gens["adjectives"]) + " " + next(gens["nouns"]) + " " + \
        next(gens["connectors"]) + " " + next(gens["verbs"]) + " " + \
        next(gens["adverbs"])

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

    results["lists"] = itertools.cycle(cfg["lists"])

    return results

def parse_file(config: Dict[str, Any], gens: Dict[str, Any], corpus_file: str) -> List[str]:

    # First, load the entire file into a dictionary,
    # then apply our custom filters to it as needed.

    paragraphs = []  # type: List[str]

    with open(corpus_file, "r") as infile:
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
        elif key == "picture":
            txt = txt      # TODO: implement pictures

        results.append(txt)

    return results

def add_md(mode: str, text: str) -> str:

    # mode means: bold, italic, etc.
    # to add a list at the end of a paragraph, * iterm one\n * item two

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
    results = []    # save the dialogs as tuples with (author, dialog)

    para = []   # we'll store the lines here to form a paragraph

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

    with open(filename, "w") as outfile:
        outfile.write(ujson.dumps(paragraphs))

def create_test_data() -> None:

    gens = load_generators(config)   # returns a dictionary of generators

    paragraphs = parse_file(config, gens, config["corpus"]["filename"])

    write_file(paragraphs, "var/test_messages.json")

config = load_config()  # type: Dict[str, Any]

if __name__ == "__main__":
    create_test_data()  # type: () -> ()
