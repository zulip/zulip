# This tool contains all of the rules that we use to decide which of
# the various emoji names in emoji-map.json we should actually use in
# autocomplete and emoji pickers.  You can't do all of them, because
# otherwise there will be a ton of duplicates alphabetically next to
# each other, which is confusing and looks bad (e.g. `angry` and
# `angry_face` or `ab` and `ab_button` will always sort next to each
# other, and you really want to just pick one).  See docs/subsystems/emoji.md for
# details on how this system works.

from collections import defaultdict
from itertools import permutations, chain

from typing import Any, Dict, List

# Emojisets that we currently support.
EMOJISETS = ['apple', 'emojione', 'google', 'twitter']

# the corresponding code point will be set to exactly these names as a
# final pass, overriding any other rules.  This is useful for cases
# where the two names are very different, users might reasonably type
# either name and be surprised when they can't find the relevant emoji.
whitelisted_names = [
    ['date', 'calendar'], ['shirt', 'tshirt'], ['cupid', 'heart_with_arrow'],
    ['tada', 'party_popper'], ['parking', 'p_button'], ['car', 'automobile'],
    ['mortar_board', 'graduation_cap'], ['cd', 'optical_disc'], ['tv', 'television'],
    ['sound', 'speaker_on'], ['mute', 'speaker_off'], ['antenna_bars', 'signal_strength'],
    ['mag_right', 'right_pointing_magnifying_glass'], ['mag', 'left_pointing_magnifying_glass'],
    ['loud_sound', 'speaker_loud'], ['rice_scene', 'moon_ceremony'],
    ['fast_up_button', 'arrow_double_up'], ['fast_down_button', 'arrow_double_down'],
    ['rewind', 'fast_reverse_button'], ['100', 'hundred_points'], ['muscle', 'flexed_biceps'],
    ['walking', 'pedestrian'], ['email', 'envelope'], ['dart', 'direct_hit'],
    ['wc', 'water_closet'], ['zap', 'high_voltage'], ['underage', 'no_one_under_eighteen'],
    ['vhs', 'videocassette'], ['bangbang', 'double_exclamation_mark'],
    ['gun', 'pistol'], ['hocho', 'kitchen_knife'], ['8ball', 'billiards'],
    ['pray', 'folded_hands'], ['cop', 'police_officer'], ['phone', 'telephone'],
    ['bee', 'honeybee'], ['lips', 'mouth'], ['boat', 'sailboat'], ['feet', 'paw_prints'],
    ['uk', 'gb'], ['alien_monster', 'space_invader'], ['reverse_button', 'arrow_backward'],
    # both github and slack remove play_button, though I think this is better
    ['play_button', 'arrow_forward'],
    # github/slack both get rid of shuffle_tracks_button, which seems wrong
    ['shuffle_tracks_button', 'twisted_rightwards_arrows'],
    ['iphone', 'mobile_phone'],  # disagrees with github/slack/emojione
    # both github and slack remove {growing,beating}_heart, not sure what I think
    ['heartpulse', 'growing_heart'], ['heartbeat', 'beating_heart'],
    # did remove cityscape_at_dusk from (city_sunset, cityscape_at_dusk)
    ['sunset', 'city_sunrise'],
    ['punch', 'oncoming_fist'],  # doesn't include facepunch
    ['+1', 'thumbs_up'],  # doesn't include thumbsup
    ['-1', 'thumbs_down'],  # doesn't include thumbsdown
    # shit, hankey. slack allows poop, shit, hankey. github calls it hankey,
    # and autocompletes for poop and shit. emojione calls it poop, and
    # autocompletes for pile_of_poo and shit.
    ['poop', 'pile_of_poo'],
    # github/slack remove cooking, but their emoji for this is an uncooked egg
    ['egg', 'cooking'],
    # to match two_{men,women}_holding_hands
    ['couple', 'man_and_woman_holding_hands'],
    # ['ocean', 'water_wave'], wave is so common that we want it to point only to :wave:
]

# We blacklist certain names in cases where the algorithms below would
# choose incorrectly which one to keep.  For example, with `football`,
# by default, our algorithm would pick just `football`, but we given
# that :rugby_football: also exists, we want to keep
# :american_football: instead.  So we just remove the shorter names here.
blacklisted_names = frozenset([
    # would be chosen by words_supersets or superstrings
    'football',  # american_football
    'post_office',  # european_post_office (there's also a japanese_post_office)
    'castle',  # european_castle (there's also a japanese_castle)
    'chart',  # chart_increasing_with_yen (should rename chart_increasing to chart)
    'loop',  # double_curly_loop (should rename curly_loop to loop)
    'massage',  # face_massage
    'bulb',  # light_bulb
    'barber',  # barber_pole
    'mens',  # mens_room
    'womens',  # womens_room
    'knife',  # kitchen_knife (hocho also maps here)
    'notes',  # musical_notes
    'beetle',  # lady_beetle
    'ab',  # ab_button (due to keeping a_button, due to the one_lettered() rule)
    'headphone',  # headphones
    'mega',  # megaphone
    'ski',  # skis
    'high_heel',  # high_heeled_shoe (so that it shows up when searching for shoe)
    # less confident about the following
    'dolls',  # japanese_dolls
    'moon',  # waxing_gibbous_moon (should rename crescent_moon to moon)
    'clapper',  # clapper_board
    'traffic_light',  # horizontal_traffic_light (there's also a vertical_traffic_light)
    'lantern',
    'red_paper_lantern',  # izakaya_lantern (in the future we should make sure
                          # red_paper_lantern finds this)

    # would be chosen by longer
    'down_button',  # arrow_down_small, I think to match the other arrow_*
                    # names. Matching what github and slack do.
    'running_shoe',  # athletic_shoe, both github and slack agree here.
    'running',  # runner. slack has both, github has running_man and running_woman, but not runner
    'o2',  # o_button
    'star2',  # glowing_star
    'bright',  # high_brightness, to match low_brightness, what github/slack do
    'dim_button',  # low_brightness, copying github/slack
    'stars',  # shooting_star. disagrees with github, slack, and emojione, but this seems better
    'nail_care',  # nail_polish. Also disagrees github/slack/emojione, is nail_polish mostly an
                 # american thing?
    'busstop',  # bus_stop
    'tophat',  # top_hat
    'old_woman',  # older_woman, following github/slack/emojione on these
    'old_man',  # older_man
    'blue_car',  # recreational_vehicle
    'litter_in_bin_sign',  # put_litter_in_its_place
    'moai',  # moyai based on github/slack
    'fuelpump',  # fuel_pump

    # names not otherwise excluded by our heuristics
    'left_arrow',  # arrow_left, to match other arrow_* shortnames
    'right_arrow',  # arrow_right
    'up_arrow',  # arrow_up
    'down_arrow',  # arrow_down
    'chequered_flag',  # checkered_flag
    'e_mail',  # e-mail
    'non_potable_water',  # non-potable_water
    'flipper',  # dolphin
])

## functions that take in a list of names at a codepoint and return a subset to exclude

def blacklisted(names):
    # type: (List[str]) -> List[str]
    return [name for name in names if name in blacklisted_names]

# 1 letter names don't currently show up in our autocomplete. Maybe should
# change our autocomplete so that a whitelist of letters do, like j (for joy), x, etc
# github uses a, ab, etc. instead of a_button, slack doesn't have any of the [letter]_buttons
def one_lettered(names):
    # type: (List[str]) -> List[str]
    if len(names) == 1:
        return []
    return [name for name in names if len(name) == 1]

# If it is an ideograph (or katakana, but we'll probably deal with that
# differently after 1.5), remove any names that don't have
# ideograph/katakana in them
def ideographless(names):
    # type: (List[str]) -> List[str]
    has_ideographs = ['ideograph' in name.split('_') or
                      'katakana' in name.split('_') for name in names]
    if not any(has_ideographs):
        return []
    return [name for name, has_ideograph in zip(names, has_ideographs) if not has_ideograph]

# In the absence of a good reason not to, we prefer :angry: over
# :angry_face:, since it's shorter and communicates the same idea.
#
# This rule is subsumed by the longer rule, but still useful for
# breaking up a hand review of the whitelist/blacklist decisions,
# since these cases are much more clear than the "longer" ones.
def word_superset(names):
    # type: (List[str]) -> List[str]
    bags_of_words = [frozenset(name.split('_')) for name in names]
    bad_names = set()
    for i, j in permutations(list(range(len(names))), 2):
        if bags_of_words[i] < bags_of_words[j]:
            bad_names.add(names[j])
    return list(bad_names)

# We prefer :dog: over :dog2: if they both point to the same unicode
# character.
#
# This rule is subsumed by the longer rule, but still useful for
# breaking up a hand review of the whitelist/blacklist decisions,
# since these cases are much more clear than the "longer" ones.
def superstring(names):
    # type: (List[str]) -> List[str]
    bad_names = set()
    for name1, name2 in permutations(names, 2):
        if name2[:len(name1)] == name1:
            bad_names.add(name2)
    return list(bad_names)

# The shorter one is usually a better name.
def longer(names):
    # type: (List[str]) -> List[str]
    lengths = [len(name) for name in names]
    min_length = min(lengths)
    return [name for name, length in zip(names, lengths) if length > min_length]

# A lot of emoji that have a color in their name aren't actually the
# right color, which is super confusing.  A big part of the reason is
# that "black" and "white" actually mean filled-in and not-filled-in
# to the Unicode committee, which is a poor choice by explains why
# something with "black" in its name might be any solid color.  Users
# want the emoji to have reasonable names, though, so we have to
# correct the names with "black" or "white" in them.
#
# Ones found after a few minutes of inspection, and after all the other filters
# have been applied. Probably others remaining.
miscolored_names = frozenset(['eight_pointed_black_star', 'large_blue_diamond',
                              'small_blue_diamond'])
def google_color_bug(names):
    # type: (List[str]) -> List[str]
    return [name for name in names if
            name[:5] == 'black' or name[:5] == 'white' or name in miscolored_names]

def emoji_names_for_picker(emoji_map):
    # type: (Dict[str, str]) -> List[str]
    codepoint_to_names = defaultdict(list)  # type: Dict[str, List[str]]
    for name, codepoint in emoji_map.items():
        codepoint_to_names[codepoint].append(name)

    # blacklisted must come first, followed by {one_lettered, ideographless}
    # Each function here returns a list of names to be removed from a list of names
    for func in [blacklisted, one_lettered, ideographless, word_superset,
                 superstring, longer, google_color_bug]:
        for codepoint, names in codepoint_to_names.items():
            codepoint_to_names[codepoint] = [name for name in names if name not in func(names)]

    for names in whitelisted_names:
        codepoint = emoji_map[names[0]]
        for name in names:
            assert (emoji_map[name] == codepoint)
        codepoint_to_names[codepoint] = names

    return sorted(list(chain.from_iterable(codepoint_to_names.values())))

# Returns a dict from categories to list of codepoints. The list of
# codepoints are sorted according to the `sort_order` as defined in
# `emoji_data`.
def generate_emoji_catalog(emoji_data):
    # type: (List[Dict[str, Any]]) -> Dict[str, List[str]]
    sort_order = {}  # type: Dict[str, int]
    emoji_catalog = {}  # type: Dict[str, List[str]]
    for emoji in emoji_data:
        if not emoji_is_universal(emoji):
            continue
        category = emoji["category"]
        codepoint = emoji["unified"].lower()
        sort_order[codepoint] = emoji["sort_order"]
        if category in emoji_catalog:
            emoji_catalog[category].append(codepoint)
        else:
            emoji_catalog[category] = [codepoint, ]
    for category in emoji_catalog:
        emoji_catalog[category].sort(key=lambda codepoint: sort_order[codepoint])
    return emoji_catalog

# Use only those names for which images are present in all
# the emoji sets so that we can switch emoji sets seemlessly.
def emoji_is_universal(emoji_dict):
    # type: (Dict[str, Any]) -> bool
    for emoji_set in EMOJISETS:
        if not emoji_dict['has_img_' + emoji_set]:
            return False
    return True

def generate_codepoint_to_name_map(names, unified_reactions_data):
    # type: (List[str], Dict[str, str]) -> Dict[str, str]
    # TODO: Decide canonical names. For now, using the names
    # generated for emoji picker. In case of multiple names
    # for the same emoji, lexicographically greater name is
    # used, for example, `thumbs_up` is used and not `+1`.
    codepoint_to_name = {}  # type: Dict[str, str]
    for name in names:
        codepoint_to_name[unified_reactions_data[name]] = name
    return codepoint_to_name

def emoji_can_be_included(emoji_dict, unified_reactions_codepoints):
    # type: (Dict[str, Any], List[str]) -> bool
    # This function returns True if an emoji in new(not included in old emoji dataset) and is
    # safe to be included. Currently emojis which are represented by a sequence of codepoints
    # or emojis with ZWJ are not to be included until we implement a mechanism for dealing with
    # their unicode versions.
    # `:fried_egg:` emoji is banned for now, due to a name collision with `:egg:` emoji in
    # `unified_reactions.json` dataset, until we completely switch to iamcal dataset.
    if emoji_dict["short_name"] == "fried_egg":
        return False
    codepoint = emoji_dict["unified"].lower()
    if '-' not in codepoint and emoji_dict["category"] != "Skin Tones" and \
            emoji_is_universal(emoji_dict) and codepoint not in unified_reactions_codepoints:
        return True
    return False

def get_new_emoji_dicts(unified_reactions_data, emoji_data):
    # type: (Dict[str, str], List[Dict[str, Any]]) -> List[Dict[str, Any]]
    unified_reactions_codepoints = [unified_reactions_data[name] for name in unified_reactions_data]
    new_emoji_dicts = []
    for emoji_dict in emoji_data:
        if emoji_can_be_included(emoji_dict, unified_reactions_codepoints):
            new_emoji_dicts.append(emoji_dict)
    return new_emoji_dicts

def get_extended_names_list(names, new_emoji_dicts):
    # type: (List[str], List[Dict[str, Any]]) -> List[str]
    extended_names_list = names[:]
    for emoji_dict in new_emoji_dicts:
        extended_names_list.append(emoji_dict["short_name"])
    return extended_names_list

def get_extended_name_to_codepoint(name_to_codepoint, new_emoji_dicts):
    # type: (Dict[str, str], List[Dict[str, Any]]) -> Dict[str, str]
    extended_name_to_codepoint = name_to_codepoint.copy()
    for emoji_dict in new_emoji_dicts:
        emoji_name = emoji_dict["short_name"]
        codepoint = emoji_dict["unified"].lower()
        extended_name_to_codepoint[emoji_name] = codepoint
    return extended_name_to_codepoint

def get_extended_codepoint_to_name(codepoint_to_name, new_emoji_dicts):
    # type: (Dict[str, str], List[Dict[str, Any]]) -> Dict[str, str]
    extended_codepoint_to_name = codepoint_to_name.copy()
    for emoji_dict in new_emoji_dicts:
        emoji_name = emoji_dict["short_name"]
        codepoint = emoji_dict["unified"].lower()
        extended_codepoint_to_name[codepoint] = emoji_name
    return extended_codepoint_to_name
