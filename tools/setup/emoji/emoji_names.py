from typing import Any, Dict

EMOJI_NAME_MAPS = {
    # seems like best emoji for happy
    '1f600': {'canonical_name': 'grinning', 'aliases': ['happy']},
    '1f603': {'canonical_name': 'smiley', 'aliases': []},
    # the google emoji for this is not great, so made People/9 'smile' and
    # renamed this one
    '1f604': {'canonical_name': 'big_smile', 'aliases': []},
    # from gemoji/unicode
    '1f601': {'canonical_name': 'grinning_face_with_smiling_eyes', 'aliases': []},
    # satisfied doesn't seem like a good description of these images
    '1f606': {'canonical_name': 'laughing', 'aliases': ['lol']},
    '1f605': {'canonical_name': 'sweat_smile', 'aliases': []},
    # laughter_tears from https://beebom.com/emoji-meanings/
    '1f602': {'canonical_name': 'joy', 'aliases': ['tears', 'laughter_tears']},
    '1f923': {'canonical_name': 'rolling_on_the_floor_laughing', 'aliases': ['rofl']},
    # not sure how the glpyhs match relaxed, but both iamcal and gemoji have it
    '263a': {'canonical_name': 'smile', 'aliases': ['relaxed']},
    '1f60a': {'canonical_name': 'blush', 'aliases': []},
    # halo comes from gemoji/unicode
    '1f607': {'canonical_name': 'innocent', 'aliases': ['halo']},
    '1f642': {'canonical_name': 'slight_smile', 'aliases': []},
    '1f643': {'canonical_name': 'upside_down', 'aliases': ['oops']},
    '1f609': {'canonical_name': 'wink', 'aliases': []},
    '1f60c': {'canonical_name': 'relieved', 'aliases': []},
    # in_love from https://beebom.com/emoji-meanings/
    '1f60d': {'canonical_name': 'heart_eyes', 'aliases': ['in_love']},
    # blow_a_kiss from https://beebom.com/emoji-meanings/
    '1f618': {'canonical_name': 'heart_kiss', 'aliases': ['blow_a_kiss']},
    '1f617': {'canonical_name': 'kiss', 'aliases': []},
    '1f619': {'canonical_name': 'kiss_smiling_eyes', 'aliases': []},
    '1f61a': {'canonical_name': 'kiss_with_blush', 'aliases': []},
    '1f60b': {'canonical_name': 'yum', 'aliases': []},
    # crazy from https://beebom.com/emoji-meanings/, seems like best emoji for
    # joking
    '1f61c': {'canonical_name': 'stuck_out_tongue_wink', 'aliases': ['joking', 'crazy']},
    '1f61d': {'canonical_name': 'stuck_out_tongue', 'aliases': []},
    # don't really need two stuck_out_tongues (see People/23), so chose
    # something else that could fit
    '1f61b': {'canonical_name': 'mischievous', 'aliases': []},
    # kaching suggested by user
    '1f911': {'canonical_name': 'money_face', 'aliases': ['kaching']},
    # arms_open seems like a natural addition
    '1f917': {'canonical_name': 'hug', 'aliases': ['arms_open']},
    '1f913': {'canonical_name': 'nerd', 'aliases': ['geek']},
    # several sites suggested this was used for "cool", but cool is taken by
    # Symbols/137
    '1f60e': {'canonical_name': 'sunglasses', 'aliases': []},
    '1f921': {'canonical_name': 'clown', 'aliases': []},
    '1f920': {'canonical_name': 'cowboy', 'aliases': []},
    # https://emojipedia.org/smirking-face/
    '1f60f': {'canonical_name': 'smirk', 'aliases': ['smug']},
    '1f612': {'canonical_name': 'unamused', 'aliases': []},
    '1f61e': {'canonical_name': 'disappointed', 'aliases': []},
    # see People/41
    '1f614': {'canonical_name': 'pensive', 'aliases': ['tired']},
    '1f61f': {'canonical_name': 'worried', 'aliases': []},
    # these seem to better capture the glyphs. This is also what :/ turns into
    # in google hangouts
    '1f615': {'canonical_name': 'oh_no', 'aliases': ['half_frown', 'concerned', 'confused']},
    '1f641': {'canonical_name': 'frown', 'aliases': ['slight_frown']},
    # sad seemed better than putting another frown as the primary name (see
    # People/37)
    '2639': {'canonical_name': 'sad', 'aliases': ['big_frown']},
    # helpless from https://emojipedia.org/persevering-face/
    '1f623': {'canonical_name': 'persevere', 'aliases': ['helpless']},
    # agony seemed like a good addition
    '1f616': {'canonical_name': 'confounded', 'aliases': ['agony']},
    # tired doesn't really match any of the 4 images, put it on People/34
    '1f62b': {'canonical_name': 'anguish', 'aliases': []},
    # distraught from https://beebom.com/emoji-meanings/
    '1f629': {'canonical_name': 'weary', 'aliases': ['distraught']},
    '1f624': {'canonical_name': 'triumph', 'aliases': []},
    '1f620': {'canonical_name': 'angry', 'aliases': []},
    # mad and grumpy from https://beebom.com/emoji-meanings/, very_angry to
    # parallel People/44 and show up in typeahead for "ang.."
    '1f621': {'canonical_name': 'rage', 'aliases': ['mad', 'grumpy', 'very_angry']},
    # blank from https://beebom.com/emoji-meanings/, speechless and poker_face
    # seemed like good ideas for this
    '1f636': {'canonical_name': 'speechless', 'aliases': ['no_mouth', 'blank', 'poker_face']},
    '1f610': {'canonical_name': 'neutral', 'aliases': []},
    '1f611': {'canonical_name': 'expressionless', 'aliases': []},
    '1f62f': {'canonical_name': 'hushed', 'aliases': []},
    '1f626': {'canonical_name': 'frowning', 'aliases': []},
    # pained from https://beebom.com/emoji-meanings/
    '1f627': {'canonical_name': 'anguished', 'aliases': ['pained']},
    # surprise from https://emojipedia.org/face-with-open-mouth/
    '1f62e': {'canonical_name': 'open_mouth', 'aliases': ['surprise']},
    '1f632': {'canonical_name': 'astonished', 'aliases': []},
    '1f635': {'canonical_name': 'dizzy', 'aliases': []},
    # the alternates are from https://emojipedia.org/flushed-face/. shame
    # doesn't work with the google emoji
    '1f633': {'canonical_name': 'flushed', 'aliases': ['embarrassed', 'blushing']},
    '1f631': {'canonical_name': 'scream', 'aliases': []},
    # scared from https://emojipedia.org/fearful-face/, shock seemed like a
    # nice addition
    '1f628': {'canonical_name': 'fear', 'aliases': ['scared', 'shock']},
    '1f630': {'canonical_name': 'cold_sweat', 'aliases': []},
    '1f622': {'canonical_name': 'cry', 'aliases': []},
    # stressed from https://beebom.com/emoji-meanings/. The internet generally
    # didn't seem to know what to make of the dissapointed_relieved name, and I
    # got the sense it wasn't an emotion that was often used. Hence replaced it
    # with exhausted.
    '1f625': {'canonical_name': 'exhausted', 'aliases': ['disappointed_relieved', 'stressed']},
    '1f924': {'canonical_name': 'drooling', 'aliases': []},
    '1f62d': {'canonical_name': 'sob', 'aliases': []},
    '1f613': {'canonical_name': 'sweat', 'aliases': []},
    '1f62a': {'canonical_name': 'sleepy', 'aliases': []},
    '1f634': {'canonical_name': 'sleeping', 'aliases': []},
    '1f644': {'canonical_name': 'rolling_eyes', 'aliases': []},
    '1f914': {'canonical_name': 'thinking', 'aliases': []},
    '1f925': {'canonical_name': 'lying', 'aliases': []},
    # seems like best emoji for nervous/anxious
    '1f62c': {'canonical_name': 'grimacing', 'aliases': ['nervous', 'anxious']},
    # zip_it from http://mashable.com/2015/10/23/ios-9-1-emoji-guide,
    # lips_sealed from https://emojipedia.org/zipper-mouth-face/, rest seemed
    # like reasonable additions
    '1f910': {'canonical_name': 'silence', 'aliases': ['quiet', 'hush', 'zip_it', 'lips_are_sealed']},
    # queasy seemed like a natural addition
    '1f922': {'canonical_name': 'nauseated', 'aliases': ['queasy']},
    '1f927': {'canonical_name': 'sneezing', 'aliases': []},
    # cant_talk from https://beebom.com/emoji-meanings/
    '1f637': {'canonical_name': 'cant_talk', 'aliases': ['mask']},
    # flu from http://mashable.com/2015/10/23/ios-9-1-emoji-guide, sick from
    # https://emojipedia.org/face-with-thermometer/, face_with_thermometer so
    # it shows up in typeahead (thermometer taken by Objects/82)
    '1f912': {'canonical_name': 'sick', 'aliases': ['flu', 'face_with_thermometer']},
    # hurt and injured from https://beebom.com/emoji-meanings/. Chose hurt as
    # primary since I think it can cover a wider set of things (e.g. emotional
    # hurt)
    '1f915': {'canonical_name': 'hurt', 'aliases': ['head_bandage', 'injured']},
    # devil from https://emojipedia.org/smiling-face-with-horns/,
    # smiling_face_with_horns from gemoji/unicode
    '1f608': {'canonical_name': 'smiling_devil', 'aliases': ['smiling_imp', 'smiling_face_with_horns']},
    # angry_devil from https://beebom.com/emoji-meanings/
    '1f47f': {'canonical_name': 'devil', 'aliases': ['imp', 'angry_devil']},
    '1f479': {'canonical_name': 'ogre', 'aliases': []},
    '1f47a': {'canonical_name': 'goblin', 'aliases': []},
    # pile_of_poo from gemoji/unicode
    '1f4a9': {'canonical_name': 'poop', 'aliases': ['pile_of_poo']},
    # alternates seemed like reasonable additions
    '1f47b': {'canonical_name': 'ghost', 'aliases': ['boo', 'spooky', 'haunted']},
    '1f480': {'canonical_name': 'skull', 'aliases': []},
    # alternates seemed like reasonable additions
    '2620': {'canonical_name': 'skull_and_crossbones', 'aliases': ['pirate', 'death', 'hazard', 'toxic', 'poison']},    # ignorelongline
    # ufo seemed like a natural addition
    '1f47d': {'canonical_name': 'alien', 'aliases': ['ufo']},
    '1f47e': {'canonical_name': 'space_invader', 'aliases': []},
    '1f916': {'canonical_name': 'robot', 'aliases': []},
    # pumpkin seemed like a natural addition
    '1f383': {'canonical_name': 'jack-o-lantern', 'aliases': ['pumpkin']},
    '1f63a': {'canonical_name': 'smiley_cat', 'aliases': []},
    '1f638': {'canonical_name': 'smile_cat', 'aliases': []},
    '1f639': {'canonical_name': 'joy_cat', 'aliases': []},
    '1f63b': {'canonical_name': 'heart_eyes_cat', 'aliases': []},
    # smug_cat to parallel People/31
    '1f63c': {'canonical_name': 'smirk_cat', 'aliases': ['smug_cat']},
    '1f63d': {'canonical_name': 'kissing_cat', 'aliases': []},
    # weary_cat from unicode/gemoji
    '1f640': {'canonical_name': 'scream_cat', 'aliases': ['weary_cat']},
    '1f63f': {'canonical_name': 'crying_cat', 'aliases': []},
    # angry_cat to better parallel People/45
    '1f63e': {'canonical_name': 'angry_cat', 'aliases': ['pouting_cat']},
    '1f450': {'canonical_name': 'open_hands', 'aliases': []},
    # praise from
    # https://emojipedia.org/person-raising-both-hands-in-celebration/
    '1f64c': {'canonical_name': 'raised_hands', 'aliases': ['praise']},
    # applause from https://emojipedia.org/clapping-hands-sign/
    '1f44f': {'canonical_name': 'clap', 'aliases': ['applause']},
    # welcome and thank_you from
    # https://emojipedia.org/person-with-folded-hands/, namaste from indian
    # culture
    '1f64f': {'canonical_name': 'pray', 'aliases': ['welcome', 'thank_you', 'namaste']},
    # done_deal seems like a natural addition
    '1f91d': {'canonical_name': 'handshake', 'aliases': ['done_deal']},
    '1f44d': {'canonical_name': '+1', 'aliases': ['thumbs_up']},
    '1f44e': {'canonical_name': '-1', 'aliases': ['thumbs_down']},
    # fist_bump from https://beebom.com/emoji-meanings/
    '1f44a': {'canonical_name': 'fist_bump', 'aliases': ['punch']},
    # used as power in social justice movements
    '270a': {'canonical_name': 'fist', 'aliases': ['power']},
    '1f91b': {'canonical_name': 'left_fist', 'aliases': []},
    '1f91c': {'canonical_name': 'right_fist', 'aliases': []},
    '1f91e': {'canonical_name': 'fingers_crossed', 'aliases': []},
    # seems to be mostly used as peace on twitter
    '270c': {'canonical_name': 'peace_sign', 'aliases': ['victory']},
    # https://emojipedia.org/sign-of-the-horns/
    '1f918': {'canonical_name': 'rock_on', 'aliases': ['sign_of_the_horns']},
    # got_it seems like a natural addition
    '1f44c': {'canonical_name': 'ok', 'aliases': ['got_it']},
    '1f448': {'canonical_name': 'point_left', 'aliases': []},
    '1f449': {'canonical_name': 'point_right', 'aliases': []},
    # :this: is a way of emphasizing the previous message. point_up instead of
    # point_up_2 so that point_up better matches the other point_*s
    '1f446': {'canonical_name': 'point_up', 'aliases': ['this']},
    '1f447': {'canonical_name': 'point_down', 'aliases': []},
    # People/114 is point_up. These seemed better than naming it point_up_2,
    # and point_of_information means it will come up in typeahead for 'point'
    '261d': {'canonical_name': 'wait_one_second', 'aliases': ['point_of_information', 'asking_a_question']},
    '270b': {'canonical_name': 'hand', 'aliases': ['raised_hand']},
    # seems like best emoji for stop, raised_back_of_hand doesn't seem that
    # useful
    '1f91a': {'canonical_name': 'stop', 'aliases': []},
    # seems like best emoji for high_five, raised_hand_with_fingers_splayed
    # doesn't seem that useful
    '1f590': {'canonical_name': 'high_five', 'aliases': ['palm']},
    # http://mashable.com/2015/10/23/ios-9-1-emoji-guide
    '1f596': {'canonical_name': 'spock', 'aliases': ['live_long_and_prosper']},
    # People/119 is a better 'hi', but 'hi' will never show up in the typeahead
    # due to 'high_five'
    '1f44b': {'canonical_name': 'wave', 'aliases': ['hello', 'hi']},
    '1f919': {'canonical_name': 'call_me', 'aliases': []},
    # flexed_biceps from gemoji/unicode, strong seemed like a good addition
    '1f4aa': {'canonical_name': 'muscle', 'aliases': []},
    '1f595': {'canonical_name': 'middle_finger', 'aliases': []},
    '270d': {'canonical_name': 'writing', 'aliases': []},
    '1f933': {'canonical_name': 'selfie', 'aliases': []},
    # Couldn't figure out why iamcal chose nail_care. unicode uses nail_polish,
    # gemoji uses both
    '1f485': {'canonical_name': 'nail_polish', 'aliases': ['nail_care']},
    '1f48d': {'canonical_name': 'ring', 'aliases': []},
    '1f484': {'canonical_name': 'lipstick', 'aliases': []},
    # People/18 seems like a better kiss for most circumstances
    '1f48b': {'canonical_name': 'lipstick_kiss', 'aliases': []},
    # mouth from gemoji/unicode
    '1f444': {'canonical_name': 'lips', 'aliases': ['mouth']},
    '1f445': {'canonical_name': 'tongue', 'aliases': []},
    '1f442': {'canonical_name': 'ear', 'aliases': []},
    '1f443': {'canonical_name': 'nose', 'aliases': []},
    # seems a better feet than Nature/86 (paw_prints)
    '1f463': {'canonical_name': 'footprints', 'aliases': ['feet']},
    '1f441': {'canonical_name': 'eye', 'aliases': []},
    # seemed the best emoji for looking
    '1f440': {'canonical_name': 'eyes', 'aliases': ['looking']},
    '1f5e3': {'canonical_name': 'speaking_head', 'aliases': []},
    # shadow seems like a good addition
    '1f464': {'canonical_name': 'silhouette', 'aliases': ['shadow']},
    # to parallel People/139
    '1f465': {'canonical_name': 'silhouettes', 'aliases': ['shadows']},
    '1f476': {'canonical_name': 'baby', 'aliases': []},
    '1f466': {'canonical_name': 'boy', 'aliases': []},
    '1f467': {'canonical_name': 'girl', 'aliases': []},
    '1f468': {'canonical_name': 'man', 'aliases': []},
    '1f469': {'canonical_name': 'woman', 'aliases': []},
    # It's used on twitter a bunch, either when showing off hair, or in a way
    # where People/144 would substitute. It'd be nice if there were another
    # emoji one could use for "good hair", but I think not a big loss to not
    # have one for zulip, and not worth the eurocentrism.
    # '1f471': {'canonical_name': 'X', 'aliases': ['person_with_blond_hair']},
    # Added elderly since I think some people prefer that term
    '1f474': {'canonical_name': 'older_man', 'aliases': ['elderly_man']},
    # Added elderly since I think some people prefer that term
    '1f475': {'canonical_name': 'older_woman', 'aliases': ['elderly_woman']},
    '1f472': {'canonical_name': 'gua_pi_mao', 'aliases': []},
    '1f473': {'canonical_name': 'turban', 'aliases': []},
    # police seems like a more polite term, and matches the unicode
    '1f46e': {'canonical_name': 'police', 'aliases': ['cop']},
    '1f477': {'canonical_name': 'construction_worker', 'aliases': []},
    '1f482': {'canonical_name': 'guard', 'aliases': []},
    # detective from gemoji, sneaky from
    # http://mashable.com/2015/10/23/ios-9-1-emoji-guide/, agent seems a
    # reasonable addition
    '1f575': {'canonical_name': 'detective', 'aliases': ['spy', 'sleuth', 'agent', 'sneaky']},
    # mrs_claus from https://emojipedia.org/mother-christmas/
    '1f936': {'canonical_name': 'mother_christmas', 'aliases': ['mrs_claus']},
    '1f385': {'canonical_name': 'santa', 'aliases': []},
    '1f478': {'canonical_name': 'princess', 'aliases': []},
    '1f934': {'canonical_name': 'prince', 'aliases': []},
    '1f470': {'canonical_name': 'bride', 'aliases': []},
    '1f935': {'canonical_name': 'tuxedo', 'aliases': []},
    '1f47c': {'canonical_name': 'angel', 'aliases': []},
    # expecting seems like a good addition
    '1f930': {'canonical_name': 'pregnant', 'aliases': ['expecting']},
    '1f647': {'canonical_name': 'bow', 'aliases': []},
    # mostly used sassily. person_tipping_hand from
    # https://emojipedia.org/information-desk-person/
    '1f481': {'canonical_name': 'information_desk_person', 'aliases': ['person_tipping_hand']},
    # no_signal to parallel People/207. Nope seems like a reasonable addition
    '1f645': {'canonical_name': 'no_signal', 'aliases': ['nope']},
    '1f646': {'canonical_name': 'ok_signal', 'aliases': []},
    # pick_me seems like a good addition
    '1f64b': {'canonical_name': 'raising_hand', 'aliases': ['pick_me']},
    '1f926': {'canonical_name': 'face_palm', 'aliases': []},
    '1f937': {'canonical_name': 'shrug', 'aliases': []},
    '1f64e': {'canonical_name': 'person_pouting', 'aliases': []},
    '1f64d': {'canonical_name': 'person_frowning', 'aliases': []},
    '1f487': {'canonical_name': 'haircut', 'aliases': []},
    '1f486': {'canonical_name': 'massage', 'aliases': []},
    # hover seems like a reasonable addition
    '1f574': {'canonical_name': 'levitating', 'aliases': ['hover']},
    '1f483': {'canonical_name': 'dancer', 'aliases': []},
    '1f57a': {'canonical_name': 'dancing', 'aliases': ['disco']},
    '1f46f': {'canonical_name': 'dancers', 'aliases': []},
    # pedestrian seems like reasonable addition
    '1f6b6': {'canonical_name': 'walking', 'aliases': ['pedestrian']},
    '1f3c3': {'canonical_name': 'running', 'aliases': ['runner']},
    '1f46b': {'canonical_name': 'man_and_woman_holding_hands', 'aliases': ['man_and_woman_couple']},
    # to parallel People/234
    '1f46d': {'canonical_name': 'two_women_holding_hands', 'aliases': ['women_couple']},
    # to parallel People/234
    '1f46c': {'canonical_name': 'two_men_holding_hands', 'aliases': ['men_couple']},
    # no need for man-woman-boy, since we aren't including the other family
    # combos
    '1f46a': {'canonical_name': 'family', 'aliases': []},
    '1f45a': {'canonical_name': 'clothing', 'aliases': []},
    '1f455': {'canonical_name': 'shirt', 'aliases': ['tshirt']},
    # denim seems like a good addition
    '1f456': {'canonical_name': 'jeans', 'aliases': ['denim']},
    # tie is shorter, and a bit more general
    '1f454': {'canonical_name': 'tie', 'aliases': []},
    '1f457': {'canonical_name': 'dress', 'aliases': []},
    '1f459': {'canonical_name': 'bikini', 'aliases': []},
    '1f458': {'canonical_name': 'kimono', 'aliases': []},
    # I feel like this is always used in the plural
    '1f460': {'canonical_name': 'high_heels', 'aliases': []},
    # flip_flops seems like a reasonable addition
    '1f461': {'canonical_name': 'sandal', 'aliases': ['flip_flops']},
    '1f462': {'canonical_name': 'boot', 'aliases': []},
    '1f45e': {'canonical_name': 'shoe', 'aliases': []},
    # running_shoe is from gemoji, sneaker seems like a reasonable addition
    '1f45f': {'canonical_name': 'athletic_shoe', 'aliases': ['sneaker', 'running_shoe']},
    '1f452': {'canonical_name': 'hat', 'aliases': []},
    '1f3a9': {'canonical_name': 'top_hat', 'aliases': []},
    # graduate seems like a better word for this
    '1f393': {'canonical_name': 'graduate', 'aliases': ['mortar_board']},
    # king and queen seem like good additions
    '1f451': {'canonical_name': 'crown', 'aliases': ['queen', 'king']},
    # safety and invincibility inspired by
    # http://mashable.com/2015/10/23/ios-9-1-emoji-guide. hard_hat and
    # rescue_worker seem like good additions
    '26d1': {'canonical_name': 'helmet', 'aliases': ['hard_hat', 'rescue_worker', 'safety_first', 'invincible']},    # ignorelongline
    # backpack from gemoji, dominates satchel on google trends
    '1f392': {'canonical_name': 'backpack', 'aliases': ['satchel']},
    '1f45d': {'canonical_name': 'pouch', 'aliases': []},
    '1f45b': {'canonical_name': 'purse', 'aliases': []},
    '1f45c': {'canonical_name': 'handbag', 'aliases': []},
    '1f4bc': {'canonical_name': 'briefcase', 'aliases': []},
    # glasses seems a more common term than eyeglasses, spectacles seems like a
    # reasonable synonym to add
    '1f453': {'canonical_name': 'glasses', 'aliases': ['spectacles']},
    '1f576': {'canonical_name': 'dark_sunglasses', 'aliases': []},
    '1f302': {'canonical_name': 'closed_umbrella', 'aliases': []},
    '2602': {'canonical_name': 'umbrella', 'aliases': []},
    # Some animals have a unicode codepoint "<animal>", some have a codepoint
    # "<animal> face", and some have both. If an animal has just a single
    # codepoint, we call it <animal>, regardless of what the codepoint is. If
    # an animal has both, we call the "<animal>" codepoint <animal>, and come
    # up with something else useful-seeming for the "<animal> face" codepoint.
    # The reason we chose "<animal> face" for the non-standard name (instead of
    # giving "<animal>" the non-standard name, as iamcal does) is because the
    # apple emoji for the "<animal>"s are too realistic. E.g. Apple's Nature/76
    # is less plausibly a puppy than this one.
    '1f436': {'canonical_name': 'puppy', 'aliases': []},
    '1f431': {'canonical_name': 'kitten', 'aliases': []},
    '1f42d': {'canonical_name': 'dormouse', 'aliases': []},
    '1f439': {'canonical_name': 'hamster', 'aliases': []},
    '1f430': {'canonical_name': 'bunny', 'aliases': []},
    '1f98a': {'canonical_name': 'fox', 'aliases': []},
    '1f43b': {'canonical_name': 'bear', 'aliases': []},
    '1f43c': {'canonical_name': 'panda', 'aliases': []},
    '1f428': {'canonical_name': 'koala', 'aliases': []},
    '1f42f': {'canonical_name': 'tiger_cub', 'aliases': []},
    '1f981': {'canonical_name': 'lion', 'aliases': []},
    '1f42e': {'canonical_name': 'calf', 'aliases': []},
    '1f437': {'canonical_name': 'piglet', 'aliases': []},
    '1f43d': {'canonical_name': 'pig_nose', 'aliases': []},
    '1f438': {'canonical_name': 'frog', 'aliases': []},
    '1f435': {'canonical_name': 'monkey_face', 'aliases': []},
    '1f648': {'canonical_name': 'see_no_evil', 'aliases': []},
    '1f649': {'canonical_name': 'hear_no_evil', 'aliases': []},
    '1f64a': {'canonical_name': 'speak_no_evil', 'aliases': []},
    '1f412': {'canonical_name': 'monkey', 'aliases': []},
    # cluck seemed like a good addition
    '1f414': {'canonical_name': 'chicken', 'aliases': ['cluck']},
    '1f427': {'canonical_name': 'penguin', 'aliases': []},
    '1f426': {'canonical_name': 'bird', 'aliases': []},
    '1f424': {'canonical_name': 'chick', 'aliases': ['baby_chick']},
    '1f423': {'canonical_name': 'hatching', 'aliases': ['hatching_chick']},
    # http://www.iemoji.com/view/emoji/668/animals-nature/front-facing-baby-chick
    '1f425': {'canonical_name': 'new_baby', 'aliases': []},
    '1f986': {'canonical_name': 'duck', 'aliases': []},
    '1f985': {'canonical_name': 'eagle', 'aliases': []},
    '1f989': {'canonical_name': 'owl', 'aliases': []},
    '1f987': {'canonical_name': 'bat', 'aliases': []},
    '1f43a': {'canonical_name': 'wolf', 'aliases': []},
    '1f417': {'canonical_name': 'boar', 'aliases': []},
    '1f434': {'canonical_name': 'pony', 'aliases': []},
    '1f984': {'canonical_name': 'unicorn', 'aliases': []},
    # buzz seemed like a reasonable addition
    '1f41d': {'canonical_name': 'bee', 'aliases': ['buzz', 'honeybee']},
    # caterpillar seemed like a reasonable addition
    '1f41b': {'canonical_name': 'bug', 'aliases': ['caterpillar']},
    '1f98b': {'canonical_name': 'butterfly', 'aliases': []},
    '1f40c': {'canonical_name': 'snail', 'aliases': []},
    # spiral_shell from unicode/gemoji, the others seemed like reasonable
    # additions
    '1f41a': {'canonical_name': 'shell', 'aliases': ['seashell', 'conch', 'spiral_shell']},
    # unicode/gemoji have lady_beetle; hopefully with ladybug we get both the
    # people that prefer lady_beetle (with beetle) and ladybug. There is also
    # ladybird, but seems a bit much for this to complete for bird.
    '1f41e': {'canonical_name': 'beetle', 'aliases': ['ladybug']},
    '1f41c': {'canonical_name': 'ant', 'aliases': []},
    '1f577': {'canonical_name': 'spider', 'aliases': []},
    '1f578': {'canonical_name': 'web', 'aliases': ['spider_web']},
    # tortoise seemed like a reasonable addition
    '1f422': {'canonical_name': 'turtle', 'aliases': ['tortoise']},
    # put in a few animal sounds, including this one
    '1f40d': {'canonical_name': 'snake', 'aliases': ['hiss']},
    '1f98e': {'canonical_name': 'lizard', 'aliases': ['gecko']},
    '1f982': {'canonical_name': 'scorpion', 'aliases': []},
    '1f980': {'canonical_name': 'crab', 'aliases': []},
    '1f991': {'canonical_name': 'squid', 'aliases': []},
    '1f419': {'canonical_name': 'octopus', 'aliases': []},
    '1f990': {'canonical_name': 'shrimp', 'aliases': []},
    '1f420': {'canonical_name': 'tropical_fish', 'aliases': []},
    '1f41f': {'canonical_name': 'fish', 'aliases': []},
    '1f421': {'canonical_name': 'blowfish', 'aliases': []},
    '1f42c': {'canonical_name': 'dolphin', 'aliases': ['flipper']},
    '1f988': {'canonical_name': 'shark', 'aliases': []},
    '1f433': {'canonical_name': 'whale', 'aliases': []},
    # https://emojipedia.org/whale/
    '1f40b': {'canonical_name': 'humpback_whale', 'aliases': []},
    '1f40a': {'canonical_name': 'crocodile', 'aliases': []},
    '1f406': {'canonical_name': 'leopard', 'aliases': []},
    '1f405': {'canonical_name': 'tiger', 'aliases': []},
    '1f403': {'canonical_name': 'water_buffalo', 'aliases': []},
    '1f402': {'canonical_name': 'ox', 'aliases': ['bull']},
    '1f404': {'canonical_name': 'cow', 'aliases': []},
    '1f98c': {'canonical_name': 'deer', 'aliases': []},
    # https://emojipedia.org/dromedary-camel/
    '1f42a': {'canonical_name': 'arabian_camel', 'aliases': []},
    '1f42b': {'canonical_name': 'camel', 'aliases': []},
    '1f418': {'canonical_name': 'elephant', 'aliases': []},
    '1f98f': {'canonical_name': 'rhinoceros', 'aliases': []},
    '1f98d': {'canonical_name': 'gorilla', 'aliases': []},
    '1f40e': {'canonical_name': 'horse', 'aliases': []},
    '1f416': {'canonical_name': 'pig', 'aliases': ['oink']},
    '1f410': {'canonical_name': 'goat', 'aliases': []},
    '1f40f': {'canonical_name': 'ram', 'aliases': []},
    '1f411': {'canonical_name': 'sheep', 'aliases': ['baa']},
    '1f415': {'canonical_name': 'dog', 'aliases': ['woof']},
    '1f429': {'canonical_name': 'poodle', 'aliases': []},
    '1f408': {'canonical_name': 'cat', 'aliases': ['meow']},
    # alarm seemed like a fun addition
    '1f413': {'canonical_name': 'rooster', 'aliases': ['alarm', 'cock-a-doodle-doo']},
    '1f983': {'canonical_name': 'turkey', 'aliases': []},
    '1f54a': {'canonical_name': 'dove', 'aliases': ['dove_of_peace']},
    '1f407': {'canonical_name': 'rabbit', 'aliases': []},
    '1f401': {'canonical_name': 'mouse', 'aliases': []},
    '1f400': {'canonical_name': 'rat', 'aliases': []},
    '1f43f': {'canonical_name': 'chipmunk', 'aliases': []},
    # paws seemed like reasonable addition. Put feet at People/135
    '1f43e': {'canonical_name': 'paw_prints', 'aliases': ['paws']},
    '1f409': {'canonical_name': 'dragon', 'aliases': []},
    '1f432': {'canonical_name': 'dragon_face', 'aliases': []},
    '1f335': {'canonical_name': 'cactus', 'aliases': []},
    '1f384': {'canonical_name': 'holiday_tree', 'aliases': []},
    '1f332': {'canonical_name': 'evergreen_tree', 'aliases': []},
    '1f333': {'canonical_name': 'tree', 'aliases': ['deciduous_tree']},
    '1f334': {'canonical_name': 'palm_tree', 'aliases': []},
    # sprout seemed like a reasonable addition
    '1f331': {'canonical_name': 'seedling', 'aliases': ['sprout']},
    # seemed like the best emoji for plant
    '1f33f': {'canonical_name': 'herb', 'aliases': ['plant']},
    # clover seemed like a reasonable addition
    '2618': {'canonical_name': 'shamrock', 'aliases': ['clover']},
    # lucky seems more useful
    '1f340': {'canonical_name': 'lucky', 'aliases': ['four_leaf_clover']},
    '1f38d': {'canonical_name': 'bamboo', 'aliases': []},
    # https://emojipedia.org/tanabata-tree/
    '1f38b': {'canonical_name': 'wish_tree', 'aliases': ['tanabata_tree']},
    # seemed like good additions. Used fall instead of autumn, since don't have
    # the rest of the seasons, and could imagine someone using both meanings of
    # fall.
    '1f343': {'canonical_name': 'leaves', 'aliases': ['wind', 'fall']},
    '1f342': {'canonical_name': 'fallen_leaf', 'aliases': []},
    '1f341': {'canonical_name': 'maple_leaf', 'aliases': []},
    '1f344': {'canonical_name': 'mushroom', 'aliases': []},
    # harvest seems more useful
    '1f33e': {'canonical_name': 'harvest', 'aliases': ['ear_of_rice']},
    '1f490': {'canonical_name': 'bouquet', 'aliases': []},
    # seems like the best emoji for flower
    '1f337': {'canonical_name': 'tulip', 'aliases': ['flower']},
    '1f339': {'canonical_name': 'rose', 'aliases': []},
    # crushed suggest by a user
    '1f940': {'canonical_name': 'wilted_flower', 'aliases': ['crushed']},
    '1f33b': {'canonical_name': 'sunflower', 'aliases': []},
    '1f33c': {'canonical_name': 'blossom', 'aliases': []},
    '1f338': {'canonical_name': 'cherry_blossom', 'aliases': []},
    '1f33a': {'canonical_name': 'hibiscus', 'aliases': []},
    '1f30e': {'canonical_name': 'earth_americas', 'aliases': []},
    '1f30d': {'canonical_name': 'earth_africa', 'aliases': []},
    '1f30f': {'canonical_name': 'earth_asia', 'aliases': []},
    '1f315': {'canonical_name': 'full_moon', 'aliases': []},
    # too many useless moons. Don't seem to get much use on twitter, and clog
    # up typeahead for moon.
    # '1f316': {'canonical_name': 'X', 'aliases': ['waning_crescent_moon']},
    # '1f317': {'canonical_name': 'X', 'aliases': ['last_quarter_moon']},
    # '1f318': {'canonical_name': 'X', 'aliases': ['waning_crescent_moon']},
    '1f311': {'canonical_name': 'new_moon', 'aliases': []},
    # '1f312': {'canonical_name': 'X', 'aliases': ['waxing_crescent_moon']},
    # '1f313': {'canonical_name': 'X', 'aliases': ['first_quarter_moon']},
    '1f314': {'canonical_name': 'waxing_moon', 'aliases': []},
    '1f31a': {'canonical_name': 'new_moon_face', 'aliases': []},
    '1f31d': {'canonical_name': 'moon_face', 'aliases': []},
    '1f31e': {'canonical_name': 'sun_face', 'aliases': []},
    # goodnight seems way more useful
    '1f31b': {'canonical_name': 'goodnight', 'aliases': []},
    # '1f31c': {'canonical_name': 'X', 'aliases': ['last_quarter_moon_with_face']},
    # seems like the best emoji for moon
    '1f319': {'canonical_name': 'moon', 'aliases': []},
    # dizzy taken by People/54, had to come up with something else
    '1f4ab': {'canonical_name': 'seeing_stars', 'aliases': []},
    '2b50': {'canonical_name': 'star', 'aliases': []},
    # glowing_star from gemoji/unicode
    '1f31f': {'canonical_name': 'glowing_star', 'aliases': []},
    # glamour seems like a reasonable addition
    '2728': {'canonical_name': 'sparkles', 'aliases': ['glamour']},
    # high_voltage from gemoji/unicode
    '26a1': {'canonical_name': 'high_voltage', 'aliases': ['zap']},
    # https://emojipedia.org/fire/
    '1f525': {'canonical_name': 'fire', 'aliases': ['lit', 'hot', 'flame']},
    # explosion and crash seem like reasonable additions
    '1f4a5': {'canonical_name': 'boom', 'aliases': ['explosion', 'crash', 'collision']},
    # meteor seems like a reasonable addition
    '2604': {'canonical_name': 'comet', 'aliases': ['meteor']},
    '2600': {'canonical_name': 'sunny', 'aliases': []},
    '1f324': {'canonical_name': 'mostly_sunny', 'aliases': []},
    # partly_cloudy for the glass half empty people
    '26c5': {'canonical_name': 'partly_sunny', 'aliases': ['partly_cloudy']},
    '1f325': {'canonical_name': 'cloudy', 'aliases': []},
    # sunshowers seems like a more fun term
    '1f326': {'canonical_name': 'sunshowers', 'aliases': ['sun_and_rain', 'partly_sunny_with_rain']},
    # pride and lgbtq seem like reasonable additions
    '1f308': {'canonical_name': 'rainbow', 'aliases': ['pride', 'lgbtq']},
    # overcast seems like a good addition
    '2601': {'canonical_name': 'cloud', 'aliases': ['overcast']},
    # suggested by user typing these into their typeahead.
    '1f327': {'canonical_name': 'rainy', 'aliases': ['soaked', 'drenched']},
    # thunderstorm seems better for this emoji, and thunder_and_rain more
    # evocative than thunder_cloud_and_rain
    '26c8': {'canonical_name': 'thunderstorm', 'aliases': ['thunder_and_rain']},
    # lightning_storm seemed better than lightning_cloud
    '1f329': {'canonical_name': 'lightning', 'aliases': ['lightning_storm']},
    # snowy to parallel sunny, cloudy, etc; snowstorm seems like a good
    # addition
    '1f328': {'canonical_name': 'snowy', 'aliases': ['snowstorm']},
    '2603': {'canonical_name': 'snowman', 'aliases': []},
    # don't need two snowmen. frosty is nice because it's a weather (primary
    # benefit) and also a snowman (one that suffered from not having snow, in
    # fact)
    '26c4': {'canonical_name': 'frosty', 'aliases': []},
    '2744': {'canonical_name': 'snowflake', 'aliases': []},
    # the internet didn't seem to have a good use for this emoji. windy is a
    # good weather that is otherwise not represented. mother_nature from
    # https://emojipedia.org/wind-blowing-face/
    '1f32c': {'canonical_name': 'windy', 'aliases': ['mother_nature']},
    '1f4a8': {'canonical_name': 'dash', 'aliases': []},
    # tornado_cloud comes from the unicode, but e.g. gemoji drops the cloud
    '1f32a': {'canonical_name': 'tornado', 'aliases': []},
    # hazy seemed like a good addition
    '1f32b': {'canonical_name': 'fog', 'aliases': ['hazy']},
    '1f30a': {'canonical_name': 'ocean', 'aliases': []},
    # drop seems better than droplet, since could be used for its other
    # meanings. water drop partly so that it shows up in typeahead for water
    '1f4a7': {'canonical_name': 'drop', 'aliases': ['water_drop']},
    '1f4a6': {'canonical_name': 'sweat_drops', 'aliases': []},
    '2614': {'canonical_name': 'umbrella_with_rain', 'aliases': []},
    '1f34f': {'canonical_name': 'green_apple', 'aliases': []},
    '1f34e': {'canonical_name': 'apple', 'aliases': []},
    '1f350': {'canonical_name': 'pear', 'aliases': []},
    # An argument for not calling this orange is to save the color for a color
    # swatch, but we can deal with that when it happens. Mandarin is from
    # https://emojipedia.org/tangerine/, also like that it has a second meaning
    '1f34a': {'canonical_name': 'orange', 'aliases': ['tangerine', 'mandarin']},
    '1f34b': {'canonical_name': 'lemon', 'aliases': []},
    '1f34c': {'canonical_name': 'banana', 'aliases': []},
    '1f349': {'canonical_name': 'watermelon', 'aliases': []},
    '1f347': {'canonical_name': 'grapes', 'aliases': []},
    '1f353': {'canonical_name': 'strawberry', 'aliases': []},
    '1f348': {'canonical_name': 'melon', 'aliases': []},
    '1f352': {'canonical_name': 'cherries', 'aliases': []},
    '1f351': {'canonical_name': 'peach', 'aliases': []},
    '1f34d': {'canonical_name': 'pineapple', 'aliases': []},
    '1f95d': {'canonical_name': 'kiwi', 'aliases': []},
    '1f951': {'canonical_name': 'avocado', 'aliases': []},
    '1f345': {'canonical_name': 'tomato', 'aliases': []},
    '1f346': {'canonical_name': 'eggplant', 'aliases': []},
    '1f952': {'canonical_name': 'cucumber', 'aliases': []},
    '1f955': {'canonical_name': 'carrot', 'aliases': []},
    # maize is from unicode
    '1f33d': {'canonical_name': 'corn', 'aliases': ['maize']},
    # chili_pepper seems like a reasonable addition
    '1f336': {'canonical_name': 'hot_pepper', 'aliases': ['chili_pepper']},
    '1f954': {'canonical_name': 'potato', 'aliases': []},
    # yam seems better than sweet_potato, since we already have a potato (not a
    # strong argument, but is better on the typeahead not to have emoji that
    # share long prefixes)
    '1f360': {'canonical_name': 'yam', 'aliases': ['sweet_potato']},
    '1f330': {'canonical_name': 'chestnut', 'aliases': []},
    '1f95c': {'canonical_name': 'peanuts', 'aliases': []},
    '1f36f': {'canonical_name': 'honey', 'aliases': []},
    '1f950': {'canonical_name': 'croissant', 'aliases': []},
    '1f35e': {'canonical_name': 'bread', 'aliases': []},
    '1f956': {'canonical_name': 'baguette', 'aliases': []},
    '1f9c0': {'canonical_name': 'cheese', 'aliases': []},
    '1f95a': {'canonical_name': 'egg', 'aliases': []},
    # already have an egg in Foods/31, though I guess wouldn't be a big deal to
    # add it here.
    '1f373': {'canonical_name': 'cooking', 'aliases': []},
    '1f953': {'canonical_name': 'bacon', 'aliases': []},
    # there's no lunch and dinner, which is a small negative against adding
    # breakfast
    '1f95e': {'canonical_name': 'pancakes', 'aliases': ['breakfast']},
    # There is already shrimp in Nature/51, and tempura seems like a better
    # description
    '1f364': {'canonical_name': 'tempura', 'aliases': []},
    # drumstick seems like a better description
    '1f357': {'canonical_name': 'drumstick', 'aliases': ['poultry']},
    '1f356': {'canonical_name': 'meat', 'aliases': []},
    '1f355': {'canonical_name': 'pizza', 'aliases': []},
    '1f32d': {'canonical_name': 'hotdog', 'aliases': []},
    '1f354': {'canonical_name': 'hamburger', 'aliases': []},
    '1f35f': {'canonical_name': 'fries', 'aliases': []},
    # https://emojipedia.org/stuffed-flatbread/
    '1f959': {'canonical_name': 'doner_kebab', 'aliases': ['shawarma', 'souvlaki', 'stuffed_flatbread']},
    '1f32e': {'canonical_name': 'taco', 'aliases': []},
    '1f32f': {'canonical_name': 'burrito', 'aliases': []},
    '1f957': {'canonical_name': 'salad', 'aliases': []},
    # I think Foods/49 is a better :food:
    '1f958': {'canonical_name': 'paella', 'aliases': []},
    '1f35d': {'canonical_name': 'spaghetti', 'aliases': []},
    # seems like the best noodles? maybe this should be Foods/47? Noodles seem
    # like a bigger thing in east asia than in europe, so going with that.
    '1f35c': {'canonical_name': 'ramen', 'aliases': ['noodles']},
    # seems like the best :food:. Also a reasonable :soup:, though the google
    # one is indeed more a pot of food (the unicode) than a soup
    '1f372': {'canonical_name': 'food', 'aliases': ['soup', 'stew']},
    # naruto is actual name, and I think don't need this to autocomplete for
    # "fish"
    '1f365': {'canonical_name': 'naruto', 'aliases': []},
    '1f363': {'canonical_name': 'sushi', 'aliases': []},
    '1f371': {'canonical_name': 'bento', 'aliases': []},
    '1f35b': {'canonical_name': 'curry', 'aliases': []},
    '1f35a': {'canonical_name': 'rice', 'aliases': []},
    # onigiri is actual name, and I think don't need this to typeahead complete
    # for "rice"
    '1f359': {'canonical_name': 'onigiri', 'aliases': []},
    # leaving rice_cracker in, so that we have something for cracker
    '1f358': {'canonical_name': 'senbei', 'aliases': ['rice_cracker']},
    '1f362': {'canonical_name': 'oden', 'aliases': []},
    '1f361': {'canonical_name': 'dango', 'aliases': []},
    '1f367': {'canonical_name': 'shaved_ice', 'aliases': []},
    # seemed like the best emoji for gelato
    '1f368': {'canonical_name': 'ice_cream', 'aliases': ['gelato']},
    # already have ice_cream in Foods/60, and soft_serve seems like a
    # potentially fun emoji to have in conjunction with ice_cream. Put in
    # soft_ice_cream so it typeahead completes on ice_cream as well.
    '1f366': {'canonical_name': 'soft_serve', 'aliases': ['soft_ice_cream']},
    '1f370': {'canonical_name': 'cake', 'aliases': []},
    '1f382': {'canonical_name': 'birthday', 'aliases': []},
    # flan seems like a reasonable addition
    '1f36e': {'canonical_name': 'custard', 'aliases': ['flan']},
    '1f36d': {'canonical_name': 'lollipop', 'aliases': []},
    '1f36c': {'canonical_name': 'candy', 'aliases': []},
    '1f36b': {'canonical_name': 'chocolate', 'aliases': []},
    '1f37f': {'canonical_name': 'popcorn', 'aliases': []},
    # donut dominates doughnut on
    # https://trends.google.com/trends/explore?q=doughnut,donut
    '1f369': {'canonical_name': 'donut', 'aliases': ['doughnut']},
    '1f36a': {'canonical_name': 'cookie', 'aliases': []},
    '1f95b': {'canonical_name': 'milk', 'aliases': ['glass_of_milk']},
    '1f37c': {'canonical_name': 'baby_bottle', 'aliases': []},
    '2615': {'canonical_name': 'coffee', 'aliases': []},
    '1f375': {'canonical_name': 'tea', 'aliases': []},
    '1f376': {'canonical_name': 'sake', 'aliases': []},
    '1f37a': {'canonical_name': 'beer', 'aliases': []},
    '1f37b': {'canonical_name': 'beers', 'aliases': []},
    '1f942': {'canonical_name': 'clink', 'aliases': ['toast']},
    '1f377': {'canonical_name': 'wine', 'aliases': []},
    # tumbler means something different in india, and don't want to use
    # shot_glass given our policy of using school-age-appropriate terms
    '1f943': {'canonical_name': 'small_glass', 'aliases': []},
    '1f378': {'canonical_name': 'cocktail', 'aliases': []},
    '1f379': {'canonical_name': 'tropical_drink', 'aliases': []},
    '1f37e': {'canonical_name': 'champagne', 'aliases': []},
    '1f944': {'canonical_name': 'spoon', 'aliases': []},
    # Added eating_utensils so this would show up in typeahead for eat.
    '1f374': {'canonical_name': 'fork_and_knife', 'aliases': ['eating_utensils']},
    # Seems like the best emoji for hungry and meal. fork_and_knife_and_plate
    # is from gemoji/unicode, and I think is better than the shorter iamcal
    # version in this case. The rest just seemed like good additions.
    '1f37d': {'canonical_name': 'hungry', 'aliases': ['meal', 'table_setting', 'fork_and_knife_with_plate', 'lets_eat']},    # ignorelongline
    # most people interested in this sport call it football
    '26bd': {'canonical_name': 'football', 'aliases': ['soccer']},
    '1f3c0': {'canonical_name': 'basketball', 'aliases': []},
    # to distinguish from Activity/1, but is also the unicode name
    '1f3c8': {'canonical_name': 'american_football', 'aliases': []},
    '26be': {'canonical_name': 'baseball', 'aliases': []},
    '1f3be': {'canonical_name': 'tennis', 'aliases': []},
    '1f3d0': {'canonical_name': 'volleyball', 'aliases': []},
    '1f3c9': {'canonical_name': 'rugby', 'aliases': []},
    # https://emojipedia.org/billiards/ suggests this is actually used for
    # billiards, not for "unlucky" or "losing" or some other connotation of
    # 8ball. The unicode name is billiards.
    '1f3b1': {'canonical_name': 'billiards', 'aliases': ['pool', '8_ball']},
    # ping pong is the unicode name, and seems slightly more popular on
    # https://trends.google.com/trends/explore?q=table%20tennis,ping%20pong
    '1f3d3': {'canonical_name': 'ping_pong', 'aliases': ['table_tennis']},
    '1f3f8': {'canonical_name': 'badminton', 'aliases': []},
    # gooooooooal seems more useful of a name, though arguably this isn't the
    # best emoji for it
    '1f945': {'canonical_name': 'gooooooooal', 'aliases': ['goal']},
    '1f3d2': {'canonical_name': 'ice_hockey', 'aliases': []},
    '1f3d1': {'canonical_name': 'field_hockey', 'aliases': []},
    # would say bat, but taken by Nature/30
    '1f3cf': {'canonical_name': 'cricket', 'aliases': ['cricket_bat']},
    # hole_in_one seems like a more useful name to have. Sent golf to
    # Activity/39
    '26f3': {'canonical_name': 'hole_in_one', 'aliases': []},
    # archery seems like a reasonable addition
    '1f3f9': {'canonical_name': 'bow_and_arrow', 'aliases': ['archery']},
    '1f3a3': {'canonical_name': 'fishing', 'aliases': []},
    '1f94a': {'canonical_name': 'boxing_glove', 'aliases': []},
    # keikogi and dogi are the actual names for this, I believe. black_belt is
    # I think a more useful name here
    '1f94b': {'canonical_name': 'black_belt', 'aliases': ['keikogi', 'dogi', 'martial_arts']},
    '26f8': {'canonical_name': 'ice_skate', 'aliases': []},
    '1f3bf': {'canonical_name': 'ski', 'aliases': []},
    '26f7': {'canonical_name': 'skier', 'aliases': []},
    '1f3c2': {'canonical_name': 'snowboarder', 'aliases': []},
    # lift is both what lifters call it, and potentially can be used more
    # generally than weight_lift. The others seemed like good additions.
    '1f3cb': {'canonical_name': 'lift', 'aliases': ['work_out', 'weight_lift', 'gym']},
    # The decisions on tenses here and in the rest of the sports section are
    # mostly from gut feel. The unicode itself is all over the place.
    '1f93a': {'canonical_name': 'fencing', 'aliases': []},
    '1f93c': {'canonical_name': 'wrestling', 'aliases': []},
    # seemed like reasonable additions
    '1f938': {'canonical_name': 'cartwheel', 'aliases': ['acrobatics', 'gymnastics', 'tumbling']},
    # seemed the best emoji for sports
    '26f9': {'canonical_name': 'ball', 'aliases': ['sports']},
    '1f93e': {'canonical_name': 'handball', 'aliases': []},
    '1f3cc': {'canonical_name': 'golf', 'aliases': []},
    '1f3c4': {'canonical_name': 'surf', 'aliases': []},
    '1f3ca': {'canonical_name': 'swim', 'aliases': []},
    '1f93d': {'canonical_name': 'water_polo', 'aliases': []},
    # rest seem like reasonable additions
    '1f6a3': {'canonical_name': 'rowboat', 'aliases': ['crew', 'sculling', 'rowing']},
    # horse_riding seems like a reasonable addition
    '1f3c7': {'canonical_name': 'horse_racing', 'aliases': ['horse_riding']},
    # at least in the US: this = cyclist, Activity/53 = mountain biker, and
    # motorcyclist = biker. Mainly from googling around and personal
    # experience. E.g. http://grammarist.com/usage/cyclist-biker/ for cyclist
    # and biker,
    # https://www.theguardian.com/lifeandstyle/2010/oct/24/bike-snobs-guide-cycling-tribes
    # for mountain biker (I've never heard the term "mountain cyclist", and
    # they are the only group on that page that gets "biker" instead of
    # "cyclist")
    '1f6b4': {'canonical_name': 'cyclist', 'aliases': []},
    # see Activity/51
    '1f6b5': {'canonical_name': 'mountain_biker', 'aliases': []},
    '1f3bd': {'canonical_name': 'running_shirt', 'aliases': []},
    # I feel like people call sports medals "medals", and military medals
    # "military medals". Also see Activity/56
    '1f3c5': {'canonical_name': 'medal', 'aliases': []},
    # See Activity/55. military_medal is the gemoji/unicode
    '1f396': {'canonical_name': 'military_medal', 'aliases': []},
    # gold and number_one seem like good additions
    '1f947': {'canonical_name': 'first_place', 'aliases': ['gold', 'number_one']},
    # to parallel Activity/57
    '1f948': {'canonical_name': 'second_place', 'aliases': ['silver']},
    # to parallel Activity/57
    '1f949': {'canonical_name': 'third_place', 'aliases': ['bronze']},
    # seemed the best emoji for winner
    '1f3c6': {'canonical_name': 'trophy', 'aliases': ['winner']},
    '1f3f5': {'canonical_name': 'rosette', 'aliases': []},
    '1f397': {'canonical_name': 'reminder_ribbon', 'aliases': []},
    # don't need ticket and admission_ticket (see Activity/64), so made one of
    # them :pass:.
    '1f3ab': {'canonical_name': 'pass', 'aliases': []},
    # see Activity/63
    '1f39f': {'canonical_name': 'ticket', 'aliases': []},
    '1f3aa': {'canonical_name': 'circus', 'aliases': []},
    '1f939': {'canonical_name': 'juggling', 'aliases': []},
    # rest seem like good additions
    '1f3ad': {'canonical_name': 'performing_arts', 'aliases': ['drama', 'theater']},
    # rest seem like good additions
    '1f3a8': {'canonical_name': 'art', 'aliases': ['palette', 'painting']},
    # action seems more useful than clapper, and clapper doesn't seem like that
    # common of a term
    '1f3ac': {'canonical_name': 'action', 'aliases': []},
    # seem like good additions
    '1f3a4': {'canonical_name': 'microphone', 'aliases': ['mike', 'mic']},
    '1f3a7': {'canonical_name': 'headphones', 'aliases': []},
    '1f3bc': {'canonical_name': 'musical_score', 'aliases': []},
    # piano seems more useful than musical_keyboard
    '1f3b9': {'canonical_name': 'piano', 'aliases': ['musical_keyboard']},
    '1f941': {'canonical_name': 'drum', 'aliases': []},
    '1f3b7': {'canonical_name': 'saxophone', 'aliases': []},
    '1f3ba': {'canonical_name': 'trumpet', 'aliases': []},
    '1f3b8': {'canonical_name': 'guitar', 'aliases': []},
    '1f3bb': {'canonical_name': 'violin', 'aliases': []},
    # dice seems more useful
    '1f3b2': {'canonical_name': 'dice', 'aliases': ['die']},
    # direct_hit from gemoji/unicode, and seems more useful. bulls_eye seemed
    # like a reasonable addition
    '1f3af': {'canonical_name': 'direct_hit', 'aliases': ['darts', 'bulls_eye']},
    # strike seemed more useful than bowling
    '1f3b3': {'canonical_name': 'strike', 'aliases': ['bowling']},
    '1f3ae': {'canonical_name': 'video_game', 'aliases': []},
    # gambling seemed more useful than slot_machine
    '1f3b0': {'canonical_name': 'slot_machine', 'aliases': []},
    # the google emoji for this is not red
    '1f697': {'canonical_name': 'car', 'aliases': []},
    # rideshare seems like a reasonable addition
    '1f695': {'canonical_name': 'taxi', 'aliases': ['rideshare']},
    # the google emoji for this is not blue. recreational_vehicle is from
    # gemoji/unicode, jeep seemed like a good addition
    '1f699': {'canonical_name': 'recreational_vehicle', 'aliases': ['jeep']},
    # school_bus seemed like a reasonable addition, even though the twitter
    # glyph for this doesn't really look like a school bus
    '1f68c': {'canonical_name': 'bus', 'aliases': ['school_bus']},
    '1f68e': {'canonical_name': 'trolley', 'aliases': []},
    '1f3ce': {'canonical_name': 'racecar', 'aliases': []},
    '1f693': {'canonical_name': 'police_car', 'aliases': []},
    '1f691': {'canonical_name': 'ambulance', 'aliases': []},
    # https://trends.google.com/trends/explore?q=fire%20truck,fire%20engine
    '1f692': {'canonical_name': 'fire_truck', 'aliases': ['fire_engine']},
    '1f690': {'canonical_name': 'minibus', 'aliases': []},
    # moving_truck and truck for Places/11 and Places/12 seem much better than
    # the iamcal names
    '1f69a': {'canonical_name': 'moving_truck', 'aliases': []},
    # see Places/11 for truck. Rest seem reasonable additions.
    '1f69b': {'canonical_name': 'truck', 'aliases': ['tractor-trailer', 'big_rig', 'semi_truck', 'transport_truck']},    # ignorelongline
    '1f69c': {'canonical_name': 'tractor', 'aliases': []},
    # kick_scooter and scooter seem better for Places/14 and Places /16 than
    # scooter and motor_scooter.
    '1f6f4': {'canonical_name': 'kick_scooter', 'aliases': []},
    '1f6b2': {'canonical_name': 'bike', 'aliases': ['bicycle']},
    # see Places/14. Called motor_bike (or bike) in India
    '1f6f5': {'canonical_name': 'scooter', 'aliases': ['motor_bike']},
    '1f3cd': {'canonical_name': 'motorcycle', 'aliases': []},
    # siren seems more useful. alert seems like a reasonable addition
    '1f6a8': {'canonical_name': 'siren', 'aliases': ['rotating_light', 'alert']},
    '1f694': {'canonical_name': 'oncoming_police_car', 'aliases': []},
    '1f68d': {'canonical_name': 'oncoming_bus', 'aliases': []},
    # car to parallel e.g. Places/1
    '1f698': {'canonical_name': 'oncoming_car', 'aliases': ['oncoming_automobile']},
    '1f696': {'canonical_name': 'oncoming_taxi', 'aliases': []},
    # ski_lift seems like a good addition
    '1f6a1': {'canonical_name': 'aerial_tramway', 'aliases': ['ski_lift']},
    # gondola seems more useful
    '1f6a0': {'canonical_name': 'gondola', 'aliases': ['mountain_cableway']},
    '1f69f': {'canonical_name': 'suspension_railway', 'aliases': []},
    # train_car seems like a reasonable addition
    '1f683': {'canonical_name': 'railway_car', 'aliases': ['train_car']},
    # this does not seem like a good emoji for train, especially compared to
    # Places/33. streetcar seems like a good addition.
    '1f68b': {'canonical_name': 'tram', 'aliases': ['streetcar']},
    '1f69e': {'canonical_name': 'mountain_railway', 'aliases': []},
    # elevated_train seems like a reasonable addition
    '1f69d': {'canonical_name': 'monorail', 'aliases': ['elevated_train']},
    # from gemoji/unicode. Also, don't thin we need two bullettrain's
    '1f684': {'canonical_name': 'high_speed_train', 'aliases': []},
    # google, wikipedia, etc prefer bullet train to bullettrain
    '1f685': {'canonical_name': 'bullet_train', 'aliases': []},
    '1f688': {'canonical_name': 'light_rail', 'aliases': []},
    '1f682': {'canonical_name': 'train', 'aliases': ['steam_locomotive']},
    # oncoming_train seems better than train2
    '1f686': {'canonical_name': 'oncoming_train', 'aliases': []},
    # saving metro for Symbols/108. The tunnel makes subway more appropriate
    # anyway.
    '1f687': {'canonical_name': 'subway', 'aliases': []},
    # all the glyphs of oncoming vehicles have names like oncoming_*. The
    # alternate names are to parallel the alternates to Places/27.
    '1f68a': {'canonical_name': 'oncoming_tram', 'aliases': ['oncoming_streetcar', 'oncoming_trolley']},
    '1f689': {'canonical_name': 'station', 'aliases': []},
    '1f681': {'canonical_name': 'helicopter', 'aliases': []},
    '1f6e9': {'canonical_name': 'small_airplane', 'aliases': []},
    '2708': {'canonical_name': 'airplane', 'aliases': []},
    # take_off seems more useful than airplane_departure. departure also seems
    # more useful than airplane_departure. Arguably departure should be the
    # primary, since arrival is probably more useful than landing in Places/42,
    # but going with this for now.
    '1f6eb': {'canonical_name': 'take_off', 'aliases': ['departure', 'airplane_departure']},
    # parallel to Places/41
    '1f6ec': {'canonical_name': 'landing', 'aliases': ['arrival', 'airplane_arrival']},
    '1f680': {'canonical_name': 'rocket', 'aliases': []},
    '1f6f0': {'canonical_name': 'satellite', 'aliases': []},
    '1f4ba': {'canonical_name': 'seat', 'aliases': []},
    '1f6f6': {'canonical_name': 'canoe', 'aliases': []},
    '26f5': {'canonical_name': 'boat', 'aliases': ['sailboat']},
    '1f6e5': {'canonical_name': 'motor_boat', 'aliases': []},
    '1f6a4': {'canonical_name': 'speedboat', 'aliases': []},
    # yatch and cruise seem like reasonable additions
    '1f6f3': {'canonical_name': 'passenger_ship', 'aliases': ['yacht', 'cruise']},
    '26f4': {'canonical_name': 'ferry', 'aliases': []},
    '1f6a2': {'canonical_name': 'ship', 'aliases': []},
    '2693': {'canonical_name': 'anchor', 'aliases': []},
    # there already is a construction in Places/82, and work_in_progress seems
    # like a useful thing to have. Construction_zone seems better than the
    # unicode construction_sign, and is there partly so this autocompletes for
    # construction.
    '1f6a7': {'canonical_name': 'work_in_progress', 'aliases': ['construction_zone']},
    # alternates from https://emojipedia.org/fuel-pump/. unicode is fuel_pump,
    # not fuelpump
    '26fd': {'canonical_name': 'fuel_pump', 'aliases': ['gas_pump', 'petrol_pump']},
    # not sure why iamcal removed the space
    '1f68f': {'canonical_name': 'bus_stop', 'aliases': []},
    # https://emojipedia.org/vertical-traffic-light/ thinks this is the more
    # common of the two traffic lights, so putting traffic_light on this one
    '1f6a6': {'canonical_name': 'traffic_light', 'aliases': ['vertical_traffic_light']},
    # see Places/57
    '1f6a5': {'canonical_name': 'horizontal_traffic_light', 'aliases': []},
    # road_trip from http://mashable.com/2015/10/23/ios-9-1-emoji-guide
    '1f5fa': {'canonical_name': 'map', 'aliases': ['world_map', 'road_trip']},
    # rock_carving, statue, and tower seem more general and less culturally
    # specific, for Places/60, 61, and 63.
    '1f5ff': {'canonical_name': 'rock_carving', 'aliases': ['moyai']},
    # new_york from https://emojipedia.org/statue-of-liberty/. see Places/60
    # for statue
    '1f5fd': {'canonical_name': 'statue', 'aliases': ['new_york', 'statue_of_liberty']},
    '26f2': {'canonical_name': 'fountain', 'aliases': []},
    # see Places/60
    '1f5fc': {'canonical_name': 'tower', 'aliases': ['tokyo_tower']},
    # choosing this as the castle since castles are a way bigger thing in
    # europe than japan, and shiro is a pretty reasonable name for Places/65
    '1f3f0': {'canonical_name': 'castle', 'aliases': []},
    # see Places/64
    '1f3ef': {'canonical_name': 'shiro', 'aliases': []},
    '1f3df': {'canonical_name': 'stadium', 'aliases': []},
    '1f3a1': {'canonical_name': 'ferris_wheel', 'aliases': []},
    '1f3a2': {'canonical_name': 'roller_coaster', 'aliases': []},
    # merry_go_round seems like a good addition
    '1f3a0': {'canonical_name': 'carousel', 'aliases': ['merry_go_round']},
    # beach_umbrella seems more useful
    '26f1': {'canonical_name': 'beach_umbrella', 'aliases': []},
    '1f3d6': {'canonical_name': 'beach', 'aliases': []},
    '1f3dd': {'canonical_name': 'island', 'aliases': []},
    '26f0': {'canonical_name': 'mountain', 'aliases': []},
    '1f3d4': {'canonical_name': 'snowy_mountain', 'aliases': []},
    # already lots of other mountains, otherwise would rename this like
    # Places/60
    '1f5fb': {'canonical_name': 'mount_fuji', 'aliases': []},
    '1f30b': {'canonical_name': 'volcano', 'aliases': []},
    '1f3dc': {'canonical_name': 'desert', 'aliases': []},
    # campsite from https://emojipedia.org/camping/, I think Places/79 is a
    # better camping
    '1f3d5': {'canonical_name': 'campsite', 'aliases': []},
    '26fa': {'canonical_name': 'tent', 'aliases': ['camping']},
    '1f6e4': {'canonical_name': 'railway_track', 'aliases': ['train_tracks']},
    # road is used much more frequently at
    # https://trends.google.com/trends/explore?q=road,motorway
    '1f6e3': {'canonical_name': 'road', 'aliases': ['motorway']},
    '1f3d7': {'canonical_name': 'construction', 'aliases': []},
    '1f3ed': {'canonical_name': 'factory', 'aliases': []},
    '1f3e0': {'canonical_name': 'house', 'aliases': []},
    # suburb seems more useful
    '1f3e1': {'canonical_name': 'suburb', 'aliases': []},
    '1f3d8': {'canonical_name': 'houses', 'aliases': []},
    # condemned seemed like a good addition
    '1f3da': {'canonical_name': 'derelict_house', 'aliases': ['condemned']},
    '1f3e2': {'canonical_name': 'office', 'aliases': []},
    '1f3ec': {'canonical_name': 'department_store', 'aliases': []},
    '1f3e3': {'canonical_name': 'japan_post', 'aliases': []},
    '1f3e4': {'canonical_name': 'post_office', 'aliases': []},
    '1f3e5': {'canonical_name': 'hospital', 'aliases': []},
    '1f3e6': {'canonical_name': 'bank', 'aliases': []},
    '1f3e8': {'canonical_name': 'hotel', 'aliases': []},
    '1f3ea': {'canonical_name': 'convenience_store', 'aliases': []},
    '1f3eb': {'canonical_name': 'school', 'aliases': []},
    '1f3e9': {'canonical_name': 'love_hotel', 'aliases': []},
    '1f492': {'canonical_name': 'wedding', 'aliases': []},
    '1f3db': {'canonical_name': 'classical_building', 'aliases': []},
    '26ea': {'canonical_name': 'church', 'aliases': []},
    '1f54c': {'canonical_name': 'mosque', 'aliases': []},
    '1f54d': {'canonical_name': 'synagogue', 'aliases': []},
    '1f54b': {'canonical_name': 'kaaba', 'aliases': []},
    '26e9': {'canonical_name': 'shinto_shrine', 'aliases': []},
    '1f5fe': {'canonical_name': 'japan', 'aliases': []},
    # rice_scene seems like a strange name to have. gemoji alternate is
    # moon_ceremony
    '1f391': {'canonical_name': 'moon_ceremony', 'aliases': []},
    '1f3de': {'canonical_name': 'national_park', 'aliases': []},
    # ocean_sunrise to parallel Places/109
    '1f305': {'canonical_name': 'sunrise', 'aliases': ['ocean_sunrise']},
    '1f304': {'canonical_name': 'mountain_sunrise', 'aliases': []},
    # shooting_star and wish seem like way better descriptions. gemoji/unicode
    # is shooting_star
    '1f320': {'canonical_name': 'shooting_star', 'aliases': ['wish']},
    '1f387': {'canonical_name': 'sparkler', 'aliases': []},
    '1f386': {'canonical_name': 'fireworks', 'aliases': []},
    '1f307': {'canonical_name': 'city_sunrise', 'aliases': []},
    '1f306': {'canonical_name': 'sunset', 'aliases': []},
    # city and skyline seem more useful than cityscape
    '1f3d9': {'canonical_name': 'city', 'aliases': ['skyline']},
    '1f303': {'canonical_name': 'night', 'aliases': []},
    # night_sky seems like a good addition
    '1f30c': {'canonical_name': 'milky_way', 'aliases': ['night_sky']},
    '1f309': {'canonical_name': 'bridge', 'aliases': []},
    '1f301': {'canonical_name': 'foggy', 'aliases': []},
    '231a': {'canonical_name': 'watch', 'aliases': []},
    # unicode/gemoji is mobile_phone. The rest seem like good additions
    '1f4f1': {'canonical_name': 'mobile_phone', 'aliases': ['smartphone', 'iphone', 'android']},
    '1f4f2': {'canonical_name': 'calling', 'aliases': []},
    # gemoji has laptop, even though the google emoji for this does not look
    # like a laptop
    '1f4bb': {'canonical_name': 'computer', 'aliases': ['laptop']},
    '2328': {'canonical_name': 'keyboard', 'aliases': []},
    '1f5a5': {'canonical_name': 'desktop_computer', 'aliases': []},
    '1f5a8': {'canonical_name': 'printer', 'aliases': []},
    # gemoji/unicode is computer_mouse
    '1f5b1': {'canonical_name': 'computer_mouse', 'aliases': []},
    '1f5b2': {'canonical_name': 'trackball', 'aliases': []},
    # arcade seems like a reasonable addition
    '1f579': {'canonical_name': 'joystick', 'aliases': ['arcade']},
    # vise seems like a reasonable addition
    '1f5dc': {'canonical_name': 'compression', 'aliases': ['vise']},
    # gold record seems more useful, idea came from
    # http://www.11points.com/Web-Tech/11_Emoji_With_Different_Meanings_Than_You_Think
    '1f4bd': {'canonical_name': 'gold_record', 'aliases': ['minidisc']},
    '1f4be': {'canonical_name': 'floppy_disk', 'aliases': []},
    '1f4bf': {'canonical_name': 'cd', 'aliases': []},
    '1f4c0': {'canonical_name': 'dvd', 'aliases': []},
    # videocassette from gemoji/unicode
    '1f4fc': {'canonical_name': 'vhs', 'aliases': ['videocassette']},
    '1f4f7': {'canonical_name': 'camera', 'aliases': []},
    # both of these seem more useful than camera_with_flash
    '1f4f8': {'canonical_name': 'taking_a_picture', 'aliases': ['say_cheese']},
    # video_recorder seems like a reasonable addition
    '1f4f9': {'canonical_name': 'video_camera', 'aliases': ['video_recorder']},
    '1f3a5': {'canonical_name': 'movie_camera', 'aliases': []},
    # seems like the best emoji for movie
    '1f4fd': {'canonical_name': 'projector', 'aliases': ['movie']},
    '1f39e': {'canonical_name': 'film', 'aliases': []},
    # both of these seem more useful than telephone_receiver
    '1f4de': {'canonical_name': 'landline', 'aliases': ['home_phone']},
    '260e': {'canonical_name': 'phone', 'aliases': ['telephone']},
    '1f4df': {'canonical_name': 'pager', 'aliases': []},
    '1f4e0': {'canonical_name': 'fax', 'aliases': []},
    '1f4fa': {'canonical_name': 'tv', 'aliases': ['television']},
    '1f4fb': {'canonical_name': 'radio', 'aliases': []},
    '1f399': {'canonical_name': 'studio_microphone', 'aliases': []},
    # volume seems more useful
    '1f39a': {'canonical_name': 'volume', 'aliases': ['level_slider']},
    '1f39b': {'canonical_name': 'control_knobs', 'aliases': []},
    '23f1': {'canonical_name': 'stopwatch', 'aliases': []},
    '23f2': {'canonical_name': 'timer', 'aliases': []},
    '23f0': {'canonical_name': 'alarm_clock', 'aliases': []},
    '1f570': {'canonical_name': 'mantelpiece_clock', 'aliases': []},
    # times_up and time_ticking seem more useful than the hourglass names
    '231b': {'canonical_name': 'times_up', 'aliases': ['hourglass_done']},
    # seems like the better hourglass. Also see Objects/36
    '23f3': {'canonical_name': 'time_ticking', 'aliases': ['hourglass']},
    '1f4e1': {'canonical_name': 'satellite_antenna', 'aliases': []},
    # seems like a reasonable addition
    '1f50b': {'canonical_name': 'battery', 'aliases': ['full_battery']},
    '1f50c': {'canonical_name': 'electric_plug', 'aliases': []},
    # light_bulb seems better and from unicode/gemoji. idea seems like a good
    # addition
    '1f4a1': {'canonical_name': 'light_bulb', 'aliases': ['bulb', 'idea']},
    '1f526': {'canonical_name': 'flashlight', 'aliases': []},
    '1f56f': {'canonical_name': 'candle', 'aliases': []},
    # seems like a reasonable addition
    '1f5d1': {'canonical_name': 'wastebasket', 'aliases': ['trash_can']},
    # http://www.iemoji.com/view/emoji/1173/objects/oil-drum
    '1f6e2': {'canonical_name': 'oil_drum', 'aliases': ['commodities']},
    # losing money from https://emojipedia.org/money-with-wings/,
    # easy_come_easy_go seems like a reasonable addition
    '1f4b8': {'canonical_name': 'losing_money', 'aliases': ['easy_come_easy_go', 'money_with_wings']},
    # I think the _bills, _banknotes etc versions of these are arguably more
    # fun to use in chat, and certainly match the glyphs better
    '1f4b5': {'canonical_name': 'dollar_bills', 'aliases': []},
    '1f4b4': {'canonical_name': 'yen_banknotes', 'aliases': []},
    '1f4b6': {'canonical_name': 'euro_banknotes', 'aliases': []},
    '1f4b7': {'canonical_name': 'pound_notes', 'aliases': []},
    '1f4b0': {'canonical_name': 'money', 'aliases': []},
    '1f4b3': {'canonical_name': 'credit_card', 'aliases': ['debit_card']},
    '1f48e': {'canonical_name': 'gem', 'aliases': ['crystal']},
    # justice seems more useful
    '2696': {'canonical_name': 'justice', 'aliases': ['scales', 'balance']},
    # fixing, at_work, and working_on_it seem like useful concepts for
    # workplace chat
    '1f527': {'canonical_name': 'fixing', 'aliases': ['wrench']},
    '1f528': {'canonical_name': 'hammer', 'aliases': ['maintenance', 'handyman', 'handywoman']},
    '2692': {'canonical_name': 'at_work', 'aliases': ['hammer_and_pick']},
    # something that might be useful for chat.zulip.org, even
    '1f6e0': {'canonical_name': 'working_on_it', 'aliases': ['hammer_and_wrench', 'tools']},
    '26cf': {'canonical_name': 'mine', 'aliases': ['pick']},
    # screw is somewhat inappropriate, but not openly so, so leaving it in
    '1f529': {'canonical_name': 'nut_and_bolt', 'aliases': ['screw']},
    '2699': {'canonical_name': 'gear', 'aliases': ['settings', 'mechanical', 'engineer']},
    '26d3': {'canonical_name': 'chains', 'aliases': []},
    '1f52b': {'canonical_name': 'gun', 'aliases': []},
    '1f4a3': {'canonical_name': 'bomb', 'aliases': []},
    # betrayed from http://www.iemoji.com/view/emoji/786/objects/kitchen-knife
    '1f52a': {'canonical_name': 'knife', 'aliases': ['hocho', 'betrayed']},
    # rated_for_violence from
    # http://www.iemoji.com/view/emoji/1085/objects/dagger. hate (also
    # suggested there) seems too strong, as does just "violence".
    '1f5e1': {'canonical_name': 'dagger', 'aliases': ['rated_for_violence']},
    '2694': {'canonical_name': 'duel', 'aliases': ['swords']},
    '1f6e1': {'canonical_name': 'shield', 'aliases': []},
    '1f6ac': {'canonical_name': 'smoking', 'aliases': []},
    '26b0': {'canonical_name': 'coffin', 'aliases': ['burial', 'grave']},
    '26b1': {'canonical_name': 'funeral_urn', 'aliases': ['cremation']},
    # amphora is too obscure, I think
    '1f3fa': {'canonical_name': 'vase', 'aliases': ['amphora']},
    '1f52e': {'canonical_name': 'crystal_ball', 'aliases': ['oracle', 'future', 'fortune_telling']},
    '1f4ff': {'canonical_name': 'prayer_beads', 'aliases': []},
    '1f488': {'canonical_name': 'barber', 'aliases': ['striped_pole']},
    # alchemy seems more useful and less obscure
    '2697': {'canonical_name': 'alchemy', 'aliases': ['alembic']},
    '1f52d': {'canonical_name': 'telescope', 'aliases': []},
    # science seems useful to have. scientist inspired by
    # http://www.iemoji.com/view/emoji/787/objects/microscope
    '1f52c': {'canonical_name': 'science', 'aliases': ['microscope', 'scientist']},
    '1f573': {'canonical_name': 'hole', 'aliases': []},
    '1f48a': {'canonical_name': 'medicine', 'aliases': ['pill']},
    '1f489': {'canonical_name': 'injection', 'aliases': ['syringe']},
    '1f321': {'canonical_name': 'temperature', 'aliases': ['thermometer', 'warm']},
    '1f6bd': {'canonical_name': 'toilet', 'aliases': []},
    '1f6b0': {'canonical_name': 'potable_water', 'aliases': ['tap_water', 'drinking_water']},
    '1f6bf': {'canonical_name': 'shower', 'aliases': []},
    '1f6c1': {'canonical_name': 'bathtub', 'aliases': []},
    '1f6c0': {'canonical_name': 'bath', 'aliases': []},
    # reception and services from
    # http://www.iemoji.com/view/emoji/1169/objects/bellhop-bell
    '1f6ce': {'canonical_name': 'bellhop_bell', 'aliases': ['reception', 'services', 'ding']},
    '1f511': {'canonical_name': 'key', 'aliases': []},
    # encrypted from http://www.iemoji.com/view/emoji/1081/objects/old-key,
    # secret from http://mashable.com/2015/10/23/ios-9-1-emoji-guide
    '1f5dd': {'canonical_name': 'secret', 'aliases': ['dungeon', 'old_key', 'encrypted', 'clue', 'hint']},
    '1f6aa': {'canonical_name': 'door', 'aliases': []},
    '1f6cb': {'canonical_name': 'living_room', 'aliases': ['furniture', 'couch_and_lamp', 'lifestyles']},
    '1f6cf': {'canonical_name': 'bed', 'aliases': ['bedroom']},
    # guestrooms from iemoji, would add hotel but taken by Places/94
    '1f6cc': {'canonical_name': 'in_bed', 'aliases': ['accommodations', 'guestrooms']},
    '1f5bc': {'canonical_name': 'picture', 'aliases': ['framed_picture']},
    '1f6cd': {'canonical_name': 'shopping_bags', 'aliases': []},
    # https://trends.google.com/trends/explore?q=shopping%20cart,shopping%20trolley
    '1f6d2': {'canonical_name': 'shopping_cart', 'aliases': ['shopping_trolley']},
    '1f381': {'canonical_name': 'gift', 'aliases': ['present']},
    # seemed like the best celebration
    '1f388': {'canonical_name': 'balloon', 'aliases': ['celebration']},
    # from gemoji/unicode
    '1f38f': {'canonical_name': 'carp_streamer', 'aliases': ['flags']},
    '1f380': {'canonical_name': 'ribbon', 'aliases': ['decoration']},
    '1f38a': {'canonical_name': 'confetti', 'aliases': ['party_ball']},
    # seemed like the best congratulations
    '1f389': {'canonical_name': 'tada', 'aliases': ['congratulations']},
    '1f38e': {'canonical_name': 'dolls', 'aliases': []},
    '1f3ee': {'canonical_name': 'lantern', 'aliases': ['izakaya_lantern']},
    '1f390': {'canonical_name': 'wind_chime', 'aliases': []},
    '2709': {'canonical_name': 'email', 'aliases': ['envelope', 'mail']},
    # seems useful for chat?
    '1f4e9': {'canonical_name': 'mail_sent', 'aliases': ['sealed']},
    '1f4e8': {'canonical_name': 'mail_received', 'aliases': []},
    '1f4e7': {'canonical_name': 'e-mail', 'aliases': []},
    '1f48c': {'canonical_name': 'love_letter', 'aliases': []},
    '1f4e5': {'canonical_name': 'inbox', 'aliases': []},
    '1f4e4': {'canonical_name': 'outbox', 'aliases': []},
    '1f4e6': {'canonical_name': 'package', 'aliases': []},
    # price_tag from iemoji
    '1f3f7': {'canonical_name': 'label', 'aliases': ['tag', 'price_tag']},
    '1f4ea': {'canonical_name': 'closed_mailbox', 'aliases': []},
    '1f4eb': {'canonical_name': 'mailbox', 'aliases': []},
    '1f4ec': {'canonical_name': 'unread_mail', 'aliases': []},
    '1f4ed': {'canonical_name': 'inbox_zero', 'aliases': ['empty_mailbox', 'no_mail']},
    '1f4ee': {'canonical_name': 'mail_dropoff', 'aliases': []},
    '1f4ef': {'canonical_name': 'horn', 'aliases': []},
    '1f4dc': {'canonical_name': 'scroll', 'aliases': []},
    # receipt seems more useful?
    '1f4c3': {'canonical_name': 'receipt', 'aliases': []},
    '1f4c4': {'canonical_name': 'document', 'aliases': ['paper', 'file', 'page']},
    '1f4d1': {'canonical_name': 'place_holder', 'aliases': []},
    '1f4ca': {'canonical_name': 'bar_chart', 'aliases': []},
    # seems like the best chart
    '1f4c8': {'canonical_name': 'chart', 'aliases': ['upwards_trend', 'growing', 'increasing']},
    '1f4c9': {'canonical_name': 'downwards_trend', 'aliases': ['shrinking', 'decreasing']},
    '1f5d2': {'canonical_name': 'spiral_notepad', 'aliases': []},
    # '1f5d3': {'canonical_name': 'X', 'aliases': ['spiral_calendar_pad']},
    # swapped the following two largely due to the emojione glyphs
    '1f4c6': {'canonical_name': 'date', 'aliases': []},
    '1f4c5': {'canonical_name': 'calendar', 'aliases': []},
    '1f4c7': {'canonical_name': 'rolodex', 'aliases': ['card_index']},
    '1f5c3': {'canonical_name': 'archive', 'aliases': []},
    '1f5f3': {'canonical_name': 'ballot_box', 'aliases': []},
    '1f5c4': {'canonical_name': 'file_cabinet', 'aliases': []},
    '1f4cb': {'canonical_name': 'clipboard', 'aliases': []},
    # don't need two file_folders, so made this organize
    '1f4c1': {'canonical_name': 'organize', 'aliases': ['file_folder']},
    '1f4c2': {'canonical_name': 'folder', 'aliases': []},
    '1f5c2': {'canonical_name': 'sort', 'aliases': []},
    '1f5de': {'canonical_name': 'newspaper', 'aliases': ['swat']},
    '1f4f0': {'canonical_name': 'headlines', 'aliases': []},
    '1f4d3': {'canonical_name': 'notebook', 'aliases': ['composition_book']},
    '1f4d4': {'canonical_name': 'decorative_notebook', 'aliases': []},
    '1f4d2': {'canonical_name': 'ledger', 'aliases': ['spiral_notebook']},
    # the glyphs here are the same as Objects/147-149 (with a different color),
    # for all but google
    '1f4d5': {'canonical_name': 'red_book', 'aliases': ['closed_book']},
    '1f4d7': {'canonical_name': 'green_book', 'aliases': []},
    '1f4d8': {'canonical_name': 'blue_book', 'aliases': []},
    '1f4d9': {'canonical_name': 'orange_book', 'aliases': []},
    '1f4da': {'canonical_name': 'books', 'aliases': []},
    '1f4d6': {'canonical_name': 'book', 'aliases': ['open_book']},
    '1f516': {'canonical_name': 'bookmark', 'aliases': []},
    '1f517': {'canonical_name': 'link', 'aliases': []},
    '1f4ce': {'canonical_name': 'paperclip', 'aliases': ['attachment']},
    # office_supplies from http://mashable.com/2015/10/23/ios-9-1-emoji-guide
    '1f587': {'canonical_name': 'office_supplies', 'aliases': ['paperclip_chain', 'linked']},
    '1f4d0': {'canonical_name': 'carpenter_square', 'aliases': ['triangular_ruler']},
    '1f4cf': {'canonical_name': 'ruler', 'aliases': ['straightedge']},
    '1f4cc': {'canonical_name': 'push_pin', 'aliases': ['thumb_tack']},
    '1f4cd': {'canonical_name': 'pin', 'aliases': ['sewing_pin']},
    '2702': {'canonical_name': 'scissors', 'aliases': []},
    '1f58a': {'canonical_name': 'pen', 'aliases': ['ballpoint_pen']},
    '1f58b': {'canonical_name': 'fountain_pen', 'aliases': []},
    # three of the four emoji sets just have a rightwards-facing objects/162
    # '2712': {'canonical_name': 'X', 'aliases': ['black_nib']},
    '1f58c': {'canonical_name': 'paintbrush', 'aliases': []},
    '1f58d': {'canonical_name': 'crayon', 'aliases': []},
    '1f4dd': {'canonical_name': 'memo', 'aliases': ['note']},
    '270f': {'canonical_name': 'pencil', 'aliases': []},
    '1f50d': {'canonical_name': 'search', 'aliases': ['find', 'magnifying_glass']},
    # '1f50e': {'canonical_name': 'X', 'aliases': ['mag_right']},
    # https://emojipedia.org/lock-with-ink-pen/
    '1f50f': {'canonical_name': 'privacy', 'aliases': ['key_signing', 'digital_security', 'protected']},
    '1f510': {'canonical_name': 'secure', 'aliases': ['lock_with_key', 'safe', 'commitment', 'loyalty']},
    '1f512': {'canonical_name': 'locked', 'aliases': []},
    '1f513': {'canonical_name': 'unlocked', 'aliases': []},
    # seems the best glyph for love and love_you
    '2764': {'canonical_name': 'heart', 'aliases': ['love', 'love_you']},
    '1f49b': {'canonical_name': 'yellow_heart', 'aliases': ['heart_of_gold']},
    '1f49a': {'canonical_name': 'green_heart', 'aliases': ['envy']},
    '1f499': {'canonical_name': 'blue_heart', 'aliases': []},
    '1f49c': {'canonical_name': 'purple_heart', 'aliases': ['bravery']},
    '1f5a4': {'canonical_name': 'black_heart', 'aliases': []},
    '1f494': {'canonical_name': 'broken_heart', 'aliases': ['heartache']},
    '2763': {'canonical_name': 'heart_exclamation', 'aliases': []},
    '1f495': {'canonical_name': 'two_hearts', 'aliases': []},
    '1f49e': {'canonical_name': 'revolving_hearts', 'aliases': []},
    '1f493': {'canonical_name': 'heartbeat', 'aliases': []},
    '1f497': {'canonical_name': 'heart_pulse', 'aliases': ['growing_heart']},
    '1f496': {'canonical_name': 'sparkling_heart', 'aliases': []},
    '1f498': {'canonical_name': 'cupid', 'aliases': ['smitten', 'heart_arrow']},
    '1f49d': {'canonical_name': 'gift_heart', 'aliases': []},
    '1f49f': {'canonical_name': 'heart_box', 'aliases': []},
    '262e': {'canonical_name': 'peace', 'aliases': []},
    '271d': {'canonical_name': 'cross', 'aliases': ['christianity']},
    '262a': {'canonical_name': 'star_and_crescent', 'aliases': ['islam']},
    '1f549': {'canonical_name': 'om', 'aliases': ['hinduism']},
    '2638': {'canonical_name': 'wheel_of_dharma', 'aliases': ['buddhism']},
    '2721': {'canonical_name': 'star_of_david', 'aliases': ['judiasm']},
    # can't find any explanation of this at all. Is an alternate star of david?
    # '1f52f': {'canonical_name': 'X', 'aliases': ['six_pointed_star']},
    '1f54e': {'canonical_name': 'menorah', 'aliases': []},
    '262f': {'canonical_name': 'yin_yang', 'aliases': []},
    '2626': {'canonical_name': 'orthodox_cross', 'aliases': []},
    '1f6d0': {'canonical_name': 'place_of_worship', 'aliases': []},
    '26ce': {'canonical_name': 'ophiuchus', 'aliases': []},
    '2648': {'canonical_name': 'aries', 'aliases': []},
    '2649': {'canonical_name': 'taurus', 'aliases': []},
    '264a': {'canonical_name': 'gemini', 'aliases': []},
    '264b': {'canonical_name': 'cancer', 'aliases': []},
    '264c': {'canonical_name': 'leo', 'aliases': []},
    '264d': {'canonical_name': 'virgo', 'aliases': []},
    '264e': {'canonical_name': 'libra', 'aliases': []},
    '264f': {'canonical_name': 'scorpius', 'aliases': []},
    '2650': {'canonical_name': 'sagittarius', 'aliases': []},
    '2651': {'canonical_name': 'capricorn', 'aliases': []},
    '2652': {'canonical_name': 'aquarius', 'aliases': []},
    '2653': {'canonical_name': 'pisces', 'aliases': []},
    '1f194': {'canonical_name': 'id', 'aliases': []},
    '269b': {'canonical_name': 'atom', 'aliases': ['physics']},
    # japanese symbol
    # '1f251': {'canonical_name': 'X', 'aliases': ['accept']},
    '2622': {'canonical_name': 'radioactive', 'aliases': ['nuclear']},
    '2623': {'canonical_name': 'biohazard', 'aliases': []},
    '1f4f4': {'canonical_name': 'phone_off', 'aliases': []},
    '1f4f3': {'canonical_name': 'vibration_mode', 'aliases': []},
    # '1f236': {'canonical_name': 'X', 'aliases': ['u6709']},
    # '1f21a': {'canonical_name': 'X', 'aliases': ['u7121']},
    # '1f238': {'canonical_name': 'X', 'aliases': ['u7533']},
    # '1f23a': {'canonical_name': 'X', 'aliases': ['u55b6']},
    # '1f237': {'canonical_name': 'X', 'aliases': ['u6708']},
    '2734': {'canonical_name': 'eight_pointed_star', 'aliases': []},
    '1f19a': {'canonical_name': 'vs', 'aliases': []},
    '1f4ae': {'canonical_name': 'white_flower', 'aliases': []},
    # '1f250': {'canonical_name': 'X', 'aliases': ['ideograph_advantage']},
    # japanese character
    # '3299': {'canonical_name': 'X', 'aliases': ['secret']},
    # '3297': {'canonical_name': 'X', 'aliases': ['congratulations']},
    # '1f234': {'canonical_name': 'X', 'aliases': ['u5408']},
    # '1f235': {'canonical_name': 'X', 'aliases': ['u6e80']},
    # '1f239': {'canonical_name': 'X', 'aliases': ['u5272']},
    # '1f232': {'canonical_name': 'X', 'aliases': ['u7981']},
    '1f170': {'canonical_name': 'a', 'aliases': []},
    '1f171': {'canonical_name': 'b', 'aliases': []},
    '1f18e': {'canonical_name': 'ab', 'aliases': []},
    '1f191': {'canonical_name': 'cl', 'aliases': []},
    '1f17e': {'canonical_name': 'o', 'aliases': []},
    '1f198': {'canonical_name': 'sos', 'aliases': []},
    # Symbols/105 seems like a better x, and looks more like the other letters
    '274c': {'canonical_name': 'cross_mark', 'aliases': ['incorrect', 'wrong']},
    '2b55': {'canonical_name': 'circle', 'aliases': []},
    '1f6d1': {'canonical_name': 'stop_sign', 'aliases': ['octagonal_sign']},
    '26d4': {'canonical_name': 'no_entry', 'aliases': ['wrong_way']},
    '1f4db': {'canonical_name': 'name_badge', 'aliases': []},
    '1f6ab': {'canonical_name': 'prohibited', 'aliases': ['not_allowed']},
    '1f4af': {'canonical_name': '100', 'aliases': ['hundred']},
    '1f4a2': {'canonical_name': 'anger', 'aliases': ['bam', 'pow']},
    '2668': {'canonical_name': 'hot_springs', 'aliases': []},
    '1f6b7': {'canonical_name': 'no_pedestrians', 'aliases': []},
    '1f6af': {'canonical_name': 'do_not_litter', 'aliases': []},
    '1f6b3': {'canonical_name': 'no_bicycles', 'aliases': []},
    '1f6b1': {'canonical_name': 'non-potable_water', 'aliases': []},
    '1f51e': {'canonical_name': 'underage', 'aliases': ['nc17']},
    '1f4f5': {'canonical_name': 'no_phones', 'aliases': []},
    '1f6ad': {'canonical_name': 'no_smoking', 'aliases': []},
    '2757': {'canonical_name': 'exclamation', 'aliases': []},
    '2755': {'canonical_name': 'grey_exclamation', 'aliases': []},
    '2753': {'canonical_name': 'question', 'aliases': []},
    '2754': {'canonical_name': 'grey_question', 'aliases': []},
    '203c': {'canonical_name': 'bangbang', 'aliases': ['double_exclamation']},
    '2049': {'canonical_name': 'interrobang', 'aliases': []},
    '1f505': {'canonical_name': 'low_brightness', 'aliases': ['dim']},
    '1f506': {'canonical_name': 'brightness', 'aliases': ['high_brightness']},
    '303d': {'canonical_name': 'part_alternation', 'aliases': []},
    '26a0': {'canonical_name': 'warning', 'aliases': ['caution', 'danger']},
    '1f6b8': {'canonical_name': 'children_crossing', 'aliases': ['school_crossing', 'drive_with_care']},
    '1f531': {'canonical_name': 'trident', 'aliases': []},
    '269c': {'canonical_name': 'fleur_de_lis', 'aliases': []},
    '1f530': {'canonical_name': 'beginner', 'aliases': []},
    '267b': {'canonical_name': 'recycle', 'aliases': []},
    # seems like the best check
    '2705': {'canonical_name': 'check', 'aliases': ['all_good', 'approved']},
    # '1f22f': {'canonical_name': 'X', 'aliases': ['u6307']},
    # stock_market seemed more useful
    '1f4b9': {'canonical_name': 'stock_market', 'aliases': []},
    '2747': {'canonical_name': 'sparkle', 'aliases': []},
    '2733': {'canonical_name': 'eight_spoked_asterisk', 'aliases': []},
    '274e': {'canonical_name': 'x', 'aliases': []},
    '1f310': {'canonical_name': 'www', 'aliases': ['globe']},
    '1f4a0': {'canonical_name': 'cute', 'aliases': ['kawaii', 'diamond_with_a_dot']},
    '24c2': {'canonical_name': 'metro', 'aliases': ['m']},
    '1f300': {'canonical_name': 'cyclone', 'aliases': ['hurricane', 'typhoon']},
    '1f4a4': {'canonical_name': 'zzz', 'aliases': []},
    '1f3e7': {'canonical_name': 'atm', 'aliases': []},
    '1f6be': {'canonical_name': 'wc', 'aliases': ['water_closet']},
    '267f': {'canonical_name': 'accessible', 'aliases': ['wheelchair', 'disabled']},
    '1f17f': {'canonical_name': 'parking', 'aliases': ['p']},
    # '1f233': {'canonical_name': 'X', 'aliases': ['u7a7a']},
    # '1f202': {'canonical_name': 'X', 'aliases': ['sa']},
    '1f6c2': {'canonical_name': 'passport_control', 'aliases': ['immigration']},
    '1f6c3': {'canonical_name': 'customs', 'aliases': []},
    '1f6c4': {'canonical_name': 'baggage_claim', 'aliases': []},
    '1f6c5': {'canonical_name': 'locker', 'aliases': ['locked_bag']},
    '1f6b9': {'canonical_name': 'mens', 'aliases': []},
    '1f6ba': {'canonical_name': 'womens', 'aliases': []},
    # seems more in line with the surrounding bathroom symbols
    '1f6bc': {'canonical_name': 'baby_change_station', 'aliases': ['nursery']},
    '1f6bb': {'canonical_name': 'restroom', 'aliases': []},
    '1f6ae': {'canonical_name': 'put_litter_in_its_place', 'aliases': []},
    '1f3a6': {'canonical_name': 'cinema', 'aliases': ['movie_theater']},
    '1f4f6': {'canonical_name': 'cell_reception', 'aliases': ['signal_strength', 'signal_bars']},
    # '1f201': {'canonical_name': 'X', 'aliases': ['koko']},
    '1f523': {'canonical_name': 'symbols', 'aliases': []},
    '2139': {'canonical_name': 'info', 'aliases': []},
    '1f524': {'canonical_name': 'abc', 'aliases': []},
    '1f521': {'canonical_name': 'abcd', 'aliases': ['alphabet']},
    '1f520': {'canonical_name': 'capital_abcd', 'aliases': ['capital_letters']},
    '1f196': {'canonical_name': 'ng', 'aliases': []},
    # from unicode/gemoji. Saving ok for People/111
    '1f197': {'canonical_name': 'squared_ok', 'aliases': []},
    # from unicode, and to parallel Symbols/135. Saving up for Symbols/171
    '1f199': {'canonical_name': 'squared_up', 'aliases': []},
    '1f192': {'canonical_name': 'cool', 'aliases': []},
    '1f195': {'canonical_name': 'new', 'aliases': []},
    '1f193': {'canonical_name': 'free', 'aliases': []},
    '0030-20e3': {'canonical_name': 'zero', 'aliases': []},
    '0031-20e3': {'canonical_name': 'one', 'aliases': []},
    '0032-20e3': {'canonical_name': 'two', 'aliases': []},
    '0033-20e3': {'canonical_name': 'three', 'aliases': []},
    '0034-20e3': {'canonical_name': 'four', 'aliases': []},
    '0035-20e3': {'canonical_name': 'five', 'aliases': []},
    '0036-20e3': {'canonical_name': 'six', 'aliases': []},
    '0037-20e3': {'canonical_name': 'seven', 'aliases': []},
    '0038-20e3': {'canonical_name': 'eight', 'aliases': []},
    '0039-20e3': {'canonical_name': 'nine', 'aliases': []},
    '1f51f': {'canonical_name': 'ten', 'aliases': []},
    '1f522': {'canonical_name': '1234', 'aliases': ['numbers']},
    '0023-20e3': {'canonical_name': 'hash', 'aliases': []},
    '002a-20e3': {'canonical_name': 'asterisk', 'aliases': []},
    '25b6': {'canonical_name': 'play', 'aliases': []},
    '23f8': {'canonical_name': 'pause', 'aliases': []},
    '23ef': {'canonical_name': 'play_pause', 'aliases': []},
    # stop taken by People/118
    '23f9': {'canonical_name': 'stop_button', 'aliases': []},
    '23fa': {'canonical_name': 'record', 'aliases': []},
    '23ed': {'canonical_name': 'next_track', 'aliases': ['skip_forward']},
    '23ee': {'canonical_name': 'previous_track', 'aliases': ['skip_back']},
    '23e9': {'canonical_name': 'fast_forward', 'aliases': []},
    '23ea': {'canonical_name': 'rewind', 'aliases': ['fast_reverse']},
    '23eb': {'canonical_name': 'double_up', 'aliases': ['fast_up']},
    '23ec': {'canonical_name': 'double_down', 'aliases': ['fast_down']},
    '25c0': {'canonical_name': 'play_reverse', 'aliases': []},
    '1f53c': {'canonical_name': 'upvote', 'aliases': ['up_button', 'increase']},
    '1f53d': {'canonical_name': 'downvote', 'aliases': ['down_button', 'decrease']},
    '27a1': {'canonical_name': 'right', 'aliases': ['east']},
    '2b05': {'canonical_name': 'left', 'aliases': ['west']},
    '2b06': {'canonical_name': 'up', 'aliases': ['north']},
    '2b07': {'canonical_name': 'down', 'aliases': ['south']},
    '2197': {'canonical_name': 'upper_right', 'aliases': ['north_east']},
    '2198': {'canonical_name': 'lower_right', 'aliases': ['south_east']},
    '2199': {'canonical_name': 'lower_left', 'aliases': ['south_west']},
    '2196': {'canonical_name': 'upper_left', 'aliases': ['north_west']},
    '2195': {'canonical_name': 'up_down', 'aliases': []},
    '2194': {'canonical_name': 'left_right', 'aliases': ['swap']},
    '21aa': {'canonical_name': 'forward', 'aliases': ['right_hook']},
    '21a9': {'canonical_name': 'reply', 'aliases': ['left_hook']},
    '2934': {'canonical_name': 'heading_up', 'aliases': []},
    '2935': {'canonical_name': 'heading_down', 'aliases': []},
    '1f500': {'canonical_name': 'shuffle', 'aliases': []},
    '1f501': {'canonical_name': 'repeat', 'aliases': []},
    '1f502': {'canonical_name': 'repeat_one', 'aliases': []},
    '1f504': {'canonical_name': 'counterclockwise', 'aliases': ['return']},
    '1f503': {'canonical_name': 'clockwise', 'aliases': []},
    '1f3b5': {'canonical_name': 'music', 'aliases': []},
    '1f3b6': {'canonical_name': 'musical_notes', 'aliases': []},
    '2795': {'canonical_name': 'plus', 'aliases': ['add']},
    '2796': {'canonical_name': 'minus', 'aliases': ['subtract']},
    '2797': {'canonical_name': 'division', 'aliases': ['divide']},
    '2716': {'canonical_name': 'multiplication', 'aliases': ['multiply']},
    '1f4b2': {'canonical_name': 'dollars', 'aliases': []},
    # There is no other exchange, so might as well generalize this
    '1f4b1': {'canonical_name': 'exchange', 'aliases': []},
    '2122': {'canonical_name': 'tm', 'aliases': ['trademark']},
    '3030': {'canonical_name': 'wavy_dash', 'aliases': []},
    '27b0': {'canonical_name': 'loop', 'aliases': []},
    # https://emojipedia.org/double-curly-loop/
    '27bf': {'canonical_name': 'double_loop', 'aliases': ['voicemail']},
    '1f51a': {'canonical_name': 'end', 'aliases': []},
    '1f519': {'canonical_name': 'back', 'aliases': []},
    '1f51b': {'canonical_name': 'on', 'aliases': []},
    '1f51d': {'canonical_name': 'top', 'aliases': []},
    '1f51c': {'canonical_name': 'soon', 'aliases': []},
    '2714': {'canonical_name': 'check_mark', 'aliases': []},
    '2611': {'canonical_name': 'checkbox', 'aliases': []},
    '1f518': {'canonical_name': 'radio_button', 'aliases': []},
    '26aa': {'canonical_name': 'white_circle', 'aliases': []},
    '26ab': {'canonical_name': 'black_circle', 'aliases': []},
    '1f534': {'canonical_name': 'red_circle', 'aliases': []},
    '1f535': {'canonical_name': 'blue_circle', 'aliases': []},
    '1f53a': {'canonical_name': 'red_triangle_up', 'aliases': []},
    '1f53b': {'canonical_name': 'red_triangle_down', 'aliases': []},
    '1f538': {'canonical_name': 'small_orange_diamond', 'aliases': []},
    '1f539': {'canonical_name': 'small_blue_diamond', 'aliases': []},
    '1f536': {'canonical_name': 'large_orange_diamond', 'aliases': []},
    '1f537': {'canonical_name': 'large_blue_diamond', 'aliases': []},
    '1f533': {'canonical_name': 'black_and_white_square', 'aliases': []},
    '1f532': {'canonical_name': 'white_and_black_square', 'aliases': []},
    '25aa': {'canonical_name': 'black_small_square', 'aliases': []},
    '25ab': {'canonical_name': 'white_small_square', 'aliases': []},
    '25fe': {'canonical_name': 'black_medium_small_square', 'aliases': []},
    '25fd': {'canonical_name': 'white_medium_small_square', 'aliases': []},
    '25fc': {'canonical_name': 'black_medium_square', 'aliases': []},
    '25fb': {'canonical_name': 'white_medium_square', 'aliases': []},
    '2b1b': {'canonical_name': 'black_large_square', 'aliases': []},
    '2b1c': {'canonical_name': 'white_large_square', 'aliases': []},
    '1f508': {'canonical_name': 'speaker', 'aliases': []},
    '1f507': {'canonical_name': 'mute', 'aliases': ['no_sound']},
    '1f509': {'canonical_name': 'softer', 'aliases': []},
    '1f50a': {'canonical_name': 'louder', 'aliases': ['sound']},
    '1f514': {'canonical_name': 'notifications', 'aliases': ['bell']},
    '1f515': {'canonical_name': 'mute_notifications', 'aliases': []},
    '1f4e3': {'canonical_name': 'megaphone', 'aliases': ['shout']},
    '1f4e2': {'canonical_name': 'loudspeaker', 'aliases': ['bullhorn']},
    '1f4ac': {'canonical_name': 'umm', 'aliases': ['speech_balloon']},
    '1f5e8': {'canonical_name': 'speech_bubble', 'aliases': []},
    '1f4ad': {'canonical_name': 'thought', 'aliases': ['dream']},
    '1f5ef': {'canonical_name': 'anger_bubble', 'aliases': []},
    '2660': {'canonical_name': 'spades', 'aliases': []},
    '2663': {'canonical_name': 'clubs', 'aliases': []},
    '2665': {'canonical_name': 'hearts', 'aliases': []},
    '2666': {'canonical_name': 'diamonds', 'aliases': []},
    '1f0cf': {'canonical_name': 'joker', 'aliases': []},
    '1f3b4': {'canonical_name': 'playing_cards', 'aliases': []},
    '1f004': {'canonical_name': 'mahjong', 'aliases': []},
    # The only use I can think of for so many clocks is to be able to use them
    # to vote on times and such in emoji reactions. But a) the experience is
    # not that great (the images are too small), b) there are issues with
    # 24-hour time (used in many countries), like what is 00:30 or 01:00
    # called, c) it's hard to make the compose typeahead experience great, and
    # d) we should have a dedicated time voting widget that takes care of
    # timezone and locale issues, and uses a digital representation.
    # '1f550': {'canonical_name': 'X', 'aliases': ['clock1']},
    # '1f551': {'canonical_name': 'X', 'aliases': ['clock2']},
    # '1f552': {'canonical_name': 'X', 'aliases': ['clock3']},
    # '1f553': {'canonical_name': 'X', 'aliases': ['clock4']},
    # '1f554': {'canonical_name': 'X', 'aliases': ['clock5']},
    # '1f555': {'canonical_name': 'X', 'aliases': ['clock6']},
    # '1f556': {'canonical_name': 'X', 'aliases': ['clock7']},
    # seems like the best choice for time
    '1f557': {'canonical_name': 'time', 'aliases': ['clock']},
    # '1f558': {'canonical_name': 'X', 'aliases': ['clock9']},
    # '1f559': {'canonical_name': 'X', 'aliases': ['clock10']},
    # '1f55a': {'canonical_name': 'X', 'aliases': ['clock11']},
    # '1f55b': {'canonical_name': 'X', 'aliases': ['clock12']},
    # '1f55c': {'canonical_name': 'X', 'aliases': ['clock130']},
    # '1f55d': {'canonical_name': 'X', 'aliases': ['clock230']},
    # '1f55e': {'canonical_name': 'X', 'aliases': ['clock330']},
    # '1f55f': {'canonical_name': 'X', 'aliases': ['clock430']},
    # '1f560': {'canonical_name': 'X', 'aliases': ['clock530']},
    # '1f561': {'canonical_name': 'X', 'aliases': ['clock630']},
    # '1f562': {'canonical_name': 'X', 'aliases': ['clock730']},
    # '1f563': {'canonical_name': 'X', 'aliases': ['clock830']},
    # '1f564': {'canonical_name': 'X', 'aliases': ['clock930']},
    # '1f565': {'canonical_name': 'X', 'aliases': ['clock1030']},
    # '1f566': {'canonical_name': 'X', 'aliases': ['clock1130']},
    # '1f567': {'canonical_name': 'X', 'aliases': ['clock1230']},
    '1f3f3': {'canonical_name': 'white_flag', 'aliases': ['surrender']},
    '1f3f4': {'canonical_name': 'black_flag', 'aliases': []},
    '1f3c1': {'canonical_name': 'checkered_flag', 'aliases': ['race', 'go', 'start']},
    '1f6a9': {'canonical_name': 'triangular_flag', 'aliases': []},
    # solidarity from iemoji
    '1f38c': {'canonical_name': 'crossed_flags', 'aliases': ['solidarity']},
}   # type: Dict[str, Dict[str, Any]]
