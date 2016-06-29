var emoji = (function () {

var exports = {};

exports.emojis = [];
exports.emojis_by_name = {};
exports.emojis_by_unicode = {};

var default_emojis = [];
var default_unicode_emojis = [];

var emoji_names = ["+1", "-1", "100", "1234", "8ball", "a", "a_button", "ab", "ab_button", "abc", "abcd", "accept", "admission_tickets", "aerial_tramway", "airplane", "airplane_arrival", "airplane_departure", "alarm_clock", "alien", "alien_monster", "ambulance", "american_football", "amphora", "anchor", "angel", "anger", "anger_symbol", "angry", "angry_face", "anguished", "anguished_face", "ant", "antenna_bars", "anticlockwise_arrows_button", "apple", "aquarius", "aries", "arrow_backward", "arrow_double_down", "arrow_double_up", "arrow_down", "arrow_down_small", "arrow_forward", "arrow_heading_down", "arrow_heading_up", "arrow_left", "arrow_lower_left", "arrow_lower_right", "arrow_right", "arrow_right_hook", "arrow_up", "arrow_up_down", "arrow_up_small", "arrow_upper_left", "arrow_upper_right", "arrows_clockwise", "arrows_counterclockwise", "art", "articulated_lorry", "artist_palette", "astonished", "astonished_face", "athletic_shoe", "atm", "atm_sign", "atom_symbol", "automobile", "b", "b_button", "baby", "baby_angel", "baby_bottle", "baby_chick", "baby_symbol", "back", "back_arrow", "backhand_index_pointing_down", "backhand_index_pointing_left", "backhand_index_pointing_right", "backhand_index_pointing_up", "badminton", "baggage_claim", "balloon", "ballot_box_with_ballot", "ballot_box_with_check", "bamboo", "banana", "bangbang", "bank", "bar_chart", "barber", "barber_pole", "baseball", "basketball", "bath", "bathtub", "battery", "beach_with_umbrella", "bear", "bear_face", "beating_heart", "bed", "bee", "beer", "beer_mug", "beers", "beetle", "beginner", "bell", "bell_with_slash", "bellhop_bell", "bento", "bento_box", "bicycle", "bicyclist", "bike", "bikini", "billiards", "bird", "birthday", "birthday_cake", "black_circle", "black_joker", "black_large_square", "black_medium_small_square", "black_medium_square", "black_nib", "black_small_square", "black_square_button", "blossom", "blowfish", "blue_book", "blue_car", "blue_circle", "blue_heart", "blush", "boar", "boat", "bomb", "book", "bookmark", "bookmark_tabs", "books", "boom", "boot", "bottle_with_popping_cork", "bouquet", "bow", "bow_and_arrow", "bowling", "boy", "bread", "bride_with_veil", "bridge_at_night", "briefcase", "bright_button", "broken_heart", "bug", "building_construction", "bulb", "bullettrain_front", "bullettrain_side", "burrito", "bus", "bus_stop", "busstop", "bust_in_silhouette", "busts_in_silhouette", "cactus", "cake", "calendar", "calling", "camel", "camera", "camera_with_flash", "camping", "cancer", "candle", "candy", "capital_abcd", "capricorn", "car", "card_file_box", "card_index", "card_index_dividers", "carousel_horse", "carp_streamer", "castle", "cat", "cat2", "cat_face", "cat_face_with_tears_of_joy", "cat_face_with_wry_smile", "cd", "chains", "chart", "chart_decreasing", "chart_increasing", "chart_increasing_with_yen", "chart_with_downwards_trend", "chart_with_upwards_trend", "checkered_flag", "cheese_wedge", "chequered_flag", "cherries", "cherry_blossom", "chestnut", "chicken", "children_crossing", "chipmunk", "chocolate_bar", "christmas_tree", "church", "cinema", "circled_accept_ideograph", "circled_advantage_ideograph", "circled_letter_m", "circus_tent", "city_sunrise", "city_sunset", "cityscape", "cityscape_at_dusk", "cl", "clap", "clapper", "clapper_board", "clapping_hands", "classical_building", "clinking_beer_mugs", "clipboard", "clock1", "clock10", "clock1030", "clock11", "clock1130", "clock12", "clock1230", "clock130", "clock2", "clock230", "clock3", "clock330", "clock4", "clock430", "clock5", "clock530", "clock6", "clock630", "clock7", "clock730", "clock8", "clock830", "clock9", "clock930", "clockwise_vertical_arrows", "closed_book", "closed_lock_with_key", "closed_mailbox_with_lowered_flag", "closed_mailbox_with_raised_flag", "closed_umbrella", "cloud", "cloud_with_lightning", "cloud_with_lightning_and_rain", "cloud_with_rain", "cloud_with_snow", "clubs", "cn", "cocktail", "cocktail_glass", "coffee", "coffin", "cold_sweat", "collision", "compression", "computer", "computer_mouse", "confetti_ball", "confounded", "confounded_face", "confused", "confused_face", "congratulations", "construction", "construction_worker", "control_knobs", "convenience_store", "cooked_rice", "cookie", "cooking", "cool", "cop", "copyright", "corn", "couch_and_lamp", "couple", "couple_with_heart", "couplekiss", "cow", "cow2", "cow_face", "crab", "crayon", "credit_card", "crescent_moon", "cricket", "crocodile", "cross_mark", "cross_mark_button", "crossed_flags", "crown", "cry", "crying_cat_face", "crying_face", "crystal_ball", "cupid", "curly_loop", "currency_exchange", "curry", "curry_rice", "custard", "customs", "cyclone", "dagger", "dancer", "dancers", "dango", "dart", "dash", "dashing", "date", "de", "deciduous_tree", "delivery_truck", "department_store", "derelict_house_building", "desert", "desert_island", "desktop_computer", "detective", "diamond_shape_with_a_dot_inside", "diamond_with_a_dot", "diamonds", "dim_button", "direct_hit", "disappointed", "disappointed_but_relieved_face", "disappointed_face", "disappointed_relieved", "dizzy", "dizzy_face", "do_not_litter", "dog", "dog2", "dog_face", "dollar", "dollar_banknote", "dolls", "dolphin", "door", "dotted_six_pointed_star", "double_curly_loop", "double_exclamation_mark", "doughnut", "dove", "down_arrow", "down_button", "dragon", "dragon_face", "dress", "dromedary_camel", "droplet", "dvd", "e-mail", "e_mail", "ear", "ear_of_corn", "ear_of_rice", "earth_africa", "earth_americas", "earth_asia", "egg", "eggplant", "eight", "eight_oclock", "eight_pointed_black_star", "eight_spoked_asterisk", "eight_thirty", "eject_button", "electric_plug", "elephant", "eleven_oclock", "eleven_thirty", "email", "end", "end_arrow", "envelope", "envelope_with_arrow", "es", "euro", "euro_banknote", "european_castle", "european_post_office", "evergreen", "evergreen_tree", "exclamation", "expressionless", "expressionless_face", "eye", "eyeglasses", "eyes", "face_massage", "face_savouring_delicious_food", "face_screaming_in_fear", "face_throwing_a_kiss", "face_with_cold_sweat", "face_with_head_bandage", "face_with_medical_mask", "face_with_open_mouth", "face_with_open_mouth_and_cold_sweat", "face_with_rolling_eyes", "face_with_steam_from_nose", "face_with_stuck_out_tongue", "face_with_stuck_out_tongue_and_tightly_closed_eyes", "face_with_stuck_out_tongue_and_winking_eye", "face_with_tears_of_joy", "face_with_thermometer", "face_without_mouth", "facepunch", "factory", "fallen_leaf", "family", "fast_down_button", "fast_forward", "fast_forword_button", "fast_reverse_button", "fast_up_button", "fax", "fax_machine", "fearful", "fearful_face", "feet", "ferris_wheel", "ferry", "field_hockey", "file_cabinet", "file_folder", "film_frames", "film_projector", "fire", "fire_engine", "fireworks", "first_quarter_moon", "first_quarter_moon_with_face", "fish", "fish_cake", "fish_cake_with_swirl", "fishing_pole", "fishing_pole_and_fish", "fist", "five", "five_oclock", "five_thirty", "flag_in_hole", "flags", "flashlight", "fleur_de_lis", "flexed_biceps", "flipper", "floppy_disk", "flower_playing_cards", "flushed", "flushed_face", "fog", "foggy", "folded_hands", "football", "footprints", "fork_and_knife", "fork_and_knife_with_plate", "fountain", "fountain_pen", "four", "four_leaf_clover", "four_oclock", "four_thirty", "fr", "frame_with_picture", "free", "french_fries", "fried_shrimp", "fries", "frog", "frog_face", "front_facing_baby_chick", "frowning", "frowning_face_with_open_mouth", "fuel_pump", "fuelpump", "full_moon", "full_moon_with_face", "funeral_urn", "game_die", "gb", "gem", "gem_stone", "gemini", "gesturing_no", "gesturing_ok", "ghost", "gift", "gift_heart", "girl", "glasses", "globe_showing_americas", "globe_showing_asia_australia", "globe_showing_europe_africa", "globe_with_meridians", "glowing_star", "goat", "goblin", "golf", "golfer", "graduation_cap", "grapes", "green_apple", "green_book", "green_heart", "grey_exclamation", "grey_question", "grimacing", "grimacing_face", "grin", "grinning", "grinning_cat_face_with_smiling_eyes", "grinning_face", "grinning_face_with_smiling_eyes", "growing_heart", "guardsman", "guitar", "gun", "haircut", "hamburger", "hammer", "hammer_and_wrench", "hamster", "hamster_face", "hand", "handbag", "hankey", "happy_person_raising_hand", "hash", "hatched_chick", "hatching_chick", "headphone", "headphones", "hear_no_evil", "heart", "heart_decoration", "heart_eyes", "heart_eyes_cat", "heart_with_arrow", "heart_with_ribbon", "heartbeat", "heartpulse", "hearts", "heavy_check_mark", "heavy_division_sign", "heavy_dollar_sign", "heavy_exclamation_mark", "heavy_large_circle", "heavy_minus_sign", "heavy_multiplication_x", "heavy_plus_sign", "helicopter", "helmet_with_white_cross", "herb", "hibiscus", "high_brightness", "high_heel", "high_heeled_shoe", "high_speed_train", "high_speed_train_with_bullet_nose", "high_voltage", "hocho", "hole", "honey_pot", "honeybee", "horizontal_traffic_light", "horse", "horse_face", "horse_racing", "hospital", "hot_dog", "hot_pepper", "hotel", "hotsprings", "hourglass", "hourglass_flowing_sand", "hourglass_with_flowing_sand", "house", "house_building", "house_buildings", "house_with_garden", "hugging_face", "hundred_points", "hushed", "hushed_face", "ice_cream", "ice_hockey_stick_and_puck", "ice_skate", "icecream", "id", "ideograph_advantage", "imp", "inbox_tray", "incoming_envelope", "index_pointing_up", "information_desk_person", "information_source", "innocent", "input_latin_letters", "input_latin_lowercase", "input_latin_uppercase", "input_numbers", "input_symbols", "interrobang", "iphone", "it", "izakaya_lantern", "jack_o_lantern", "japan", "japanese_castle", "japanese_dolls", "japanese_goblin", "japanese_ogre", "japanese_post_office", "japanese_symbol_for_beginner", "jeans", "joker", "joy", "joy_cat", "joystick", "jp", "kaaba", "key", "keycap_ten", "kimono", "kiss", "kiss_mark", "kissing", "kissing_cat", "kissing_cat_face_with_closed_eyes", "kissing_closed_eyes", "kissing_face", "kissing_face_with_closed_eyes", "kissing_face_with_smiling_eyes", "kissing_heart", "kissing_smiling_eyes", "kitchen_knife", "knife", "koala", "koko", "kr", "label", "lady_beetle", "lantern", "laptop_computer", "large_blue_circle", "large_blue_diamond", "large_orange_diamond", "last_quarter_moon", "last_quarter_moon_with_face", "last_track_button", "latin_cross", "laughing", "leaf_fluttering_in_wind", "leaves", "ledger", "left_arrow", "left_arrow_curving_right", "left_luggage", "left_pointing_magnifying_glass", "left_right_arrow", "left_speech_bubble", "leftwards_arrow_with_hook", "lemon", "leo", "leopard", "level_slider", "libra", "light_bulb", "light_rail", "link", "linked_paperclips", "lion_face", "lips", "lipstick", "litter_in_bin_sign", "lock", "lock_with_ink_pen", "lock_with_pen", "locomotive", "lollipop", "loop", "loud_sound", "loudly_crying_face", "loudspeaker", "love_hotel", "love_letter", "low_brightness", "m", "mag", "mag_right", "mahjong", "mahjong_red_dragon", "mailbox", "mailbox_closed", "mailbox_with_mail", "mailbox_with_no_mail", "man", "man_and_woman_holding_hands", "man_in_business_suit_levitating", "man_with_chinese_cap", "man_with_gua_pi_mao", "man_with_turban", "mans_shoe", "mantelpiece_clock", "map_of_japan", "maple_leaf", "mask", "massage", "meat_on_bone", "mega", "megaphone", "melon", "memo", "menorah", "mens", "mens_room", "metro", "microphone", "microscope", "middle_finger", "military_medal", "milky_way", "minibus", "minidisc", "moai", "mobile_phone", "mobile_phone_off", "mobile_phone_with_arrow", "money_bag", "money_mouth_face", "money_with_wings", "moneybag", "monkey", "monkey_face", "monorail", "moon", "moon_ceremony", "mortar_board", "mosque", "motor_boat", "motorcycle", "motorway", "mount_fuji", "mountain", "mountain_bicyclist", "mountain_biker", "mountain_cableway", "mountain_railway", "mouse", "mouse2", "mouse_face", "mouth", "movie_camera", "moyai", "muscle", "mushroom", "musical_keyboard", "musical_note", "musical_notes", "musical_score", "mute", "nail_care", "nail_polish", "name_badge", "national_park", "necktie", "negative_squared_cross_mark", "nerd_face", "neutral_face", "new", "new_moon", "new_moon_face", "new_moon_with_face", "newspaper", "next_track_button", "ng", "night_with_stars", "nine", "nine_oclock", "nine_thirty", "no_bell", "no_bicycles", "no_entry", "no_entry_sign", "no_good", "no_littering", "no_mobile_phones", "no_mouth", "no_one_under_eighteen", "no_pedestrians", "no_smoking", "non-potable_water", "non_potable_water", "nose", "notebook", "notebook_with_decorative_cover", "notes", "nut_and_bolt", "o", "o2", "o_button", "ocean", "octopus", "oden", "office", "office_building", "ogre", "oil_drum", "ok", "ok_hand", "ok_woman", "old_key", "old_man", "old_woman", "older_man", "older_woman", "om", "on", "on_arrow", "oncoming_automobile", "oncoming_bus", "oncoming_fist", "oncoming_police_car", "oncoming_taxi", "one", "one_oclock", "one_thirty", "open_book", "open_file_folder", "open_hands", "open_lock", "open_mailbox_with_lowered_flag", "open_mailbox_with_raised_flag", "open_mouth", "ophiuchus", "optical_disc", "orange_book", "outbox_tray", "ox", "p_button", "package", "page_facing_up", "page_with_curl", "pager", "paintbrush", "palm_tree", "panda_face", "paperclip", "parking", "part_alternation_mark", "partly_sunny", "party_popper", "passenger_ship", "passport_control", "pause_button", "paw_prints", "peace_symbol", "peach", "pear", "pedestrian", "pen", "pencil", "pencil2", "penguin", "pensive", "pensive_face", "performing_arts", "persevere", "persevering_face", "person_bowing", "person_frowning", "person_in_bed", "person_pouting", "person_raising_hands", "person_taking_bath", "person_with_ball", "person_with_blond_hair", "person_with_pouting_face", "phone", "pick", "pig", "pig2", "pig_face", "pig_nose", "pile_of_poo", "pill", "pine_decoration", "pineapple", "ping_pong", "pisces", "pistol", "pizza", "place_of_worship", "play_button", "play_or_pause_button", "point_down", "point_left", "point_right", "point_up", "point_up_2", "police_car", "police_cars_light", "police_officer", "poodle", "poop", "popcorn", "post_office", "postal_horn", "postbox", "pot_of_food", "potable_water", "pouch", "poultry_leg", "pound", "pound_banknote", "pouting_cat", "pouting_cat_face", "pouting_face", "pray", "prayer_beads", "princess", "printer", "prohibited", "punch", "purple_heart", "purse", "pushpin", "put_litter_in_its_place", "question", "rabbit", "rabbit2", "rabbit_face", "racehorse", "racing_car", "radio", "radio_button", "rage", "railway_car", "railway_track", "rainbow", "raised_fist", "raised_hand", "raised_hand_with_fingers_splayed", "raised_hands", "raising_hand", "ram", "ramen", "rat", "record_button", "recreational_vehicle", "recycle", "recycling_symbol", "red_apple", "red_car", "red_circle", "red_paper_lantern", "red_triangle_pointed_down", "red_triangle_pointed_up", "registered", "relaxed", "relieved", "relieved_face", "reminder_ribbon", "repeat", "repeat_button", "repeat_one", "repeat_single_button", "restroom", "reverse_button", "revolving_hearts", "rewind", "ribbon", "rice", "rice_ball", "rice_cracker", "rice_scene", "right_anger_bubble", "right_arrow", "right_arrow_curving_left", "right_pointing_magnifying_glass", "ring", "roasted_sweet_potato", "robot_face", "rocket", "rolled_up_newspaper", "roller_coaster", "rooster", "rose", "rosette", "rotating_light", "round_pushpin", "rowboat", "ru", "rugby_football", "runner", "running", "running_shirt", "running_shirt_with_sash", "running_shoe", "sa", "sagittarius", "sailboat", "sake", "sandal", "santa", "santa_claus", "satellite", "satellite_antenna", "satisfied", "saxophone", "school", "school_backpack", "school_satchel", "scissors", "scorpion", "scorpius", "scream", "scream_cat", "scroll", "seat", "secret", "see_no_evil", "seedling", "seven", "seven_oclock", "seven_thirty", "shaved_ice", "sheaf_of_rice", "sheep", "shell", "shield", "shinto_shrine", "ship", "shirt", "shit", "shoe", "shooting_star", "shopping_bags", "shortcake", "shower", "shuffle_tracks_button", "sign_of_the_horns", "signal_strength", "simple_smile", "six", "six_oclock", "six_pointed_star", "six_thirty", "ski", "skier", "skis", "skull", "sleeping", "sleeping_face", "sleepy", "sleepy_face", "slightly_frowning_face", "slightly_smiling_face", "slot_machine", "small_airplane", "small_blue_diamond", "small_orange_diamond", "small_red_triangle", "small_red_triangle_down", "smile", "smile_cat", "smiley", "smiley_cat", "smiling_cat_face_with_heart_shaped_eyes", "smiling_cat_face_with_open_mouth", "smiling_face", "smiling_face_with_halo", "smiling_face_with_heart_shaped_eyes", "smiling_face_with_horns", "smiling_face_with_open_mouth", "smiling_face_with_open_mouth_and_cold_sweat", "smiling_face_with_open_mouth_and_smiling_eyes", "smiling_face_with_open_mouth_and_tightly_closed_eyes", "smiling_face_with_smiling_eyes", "smiling_face_with_sunglasses", "smiling_imp", "smirk", "smirk_cat", "smirking_face", "smoking", "snail", "snake", "snow_capped_mountain", "snowboarder", "snowflake", "snowman", "snowman_without_snow", "sob", "soccer", "soccer_ball", "soft_ice_cream", "soon", "soon_arrow", "sos", "sound", "space_invader", "spades", "spaghetti", "sparkle", "sparkler", "sparkles", "sparkling_heart", "speak_no_evil", "speaker", "speaker_loud", "speaker_off", "speaker_on", "speaking_head", "speech_balloon", "speedboat", "spider", "spider_web", "spiral_calendar", "spiral_notepad", "spiral_shell", "sports_medal", "spouting_whale", "squared_apply_ideograph", "squared_cl", "squared_cool", "squared_divide_ideograph", "squared_empty_ideograph", "squared_exist_ideograph", "squared_finger_ideograph", "squared_free", "squared_fullness_ideograph", "squared_id", "squared_katakana_koko", "squared_katakana_sa", "squared_moon_ideograph", "squared_negation_ideograph", "squared_new", "squared_ng", "squared_ok", "squared_operating_ideograph", "squared_prohibit_ideograph", "squared_sos", "squared_together_ideograph", "squared_vs", "stadium", "star", "star2", "star_and_crescent", "stars", "station", "statue_of_liberty", "steam_locomotive", "steaming_bowl", "stew", "stop_button", "stopwatch", "straight_ruler", "strawberry", "stuck_out_tongue", "stuck_out_tongue_closed_eyes", "stuck_out_tongue_winking_eye", "studio_microphone", "sun_behind_cloud", "sun_behind_cloud_with_rain", "sun_behind_large_cloud", "sun_behind_small_cloud", "sun_with_face", "sunflower", "sunglasses", "sunny", "sunrise", "sunrise_over_mountains", "sunset", "surfer", "sushi", "suspension_railway", "sweat", "sweat_droplets", "sweat_drops", "sweat_smile", "sweet_potato", "swimmer", "symbols", "synagogue", "syringe", "t_shirt", "taco", "tada", "tanabata_tree", "tangerine", "taurus", "taxi", "tea", "teacup_without_handle", "tear_off_calendar", "telephone", "telephone_receiver", "telescope", "television", "ten_oclock", "ten_thirty", "tennis", "tent", "thermometer", "thinking_face", "thought_balloon", "three", "three_oclock", "three_thirty", "thumbs_down", "thumbs_up", "thumbsdown", "thumbsup", "ticket", "tiger", "tiger2", "tiger_face", "timer_clock", "tired_face", "tm", "toilet", "tokyo_tower", "tomato", "tongue", "top", "top_arrow", "top_hat", "tophat", "tornado", "trackball", "tractor", "traffic_light", "train", "train2", "tram", "tram_car", "triangular_flag", "triangular_flag_on_post", "triangular_ruler", "trident", "trident_emblem", "triumph", "trolleybus", "trophy", "tropical_drink", "tropical_fish", "truck", "trumpet", "tshirt", "tulip", "turkey", "turtle", "tv", "twelve_oclock", "twelve_thirty", "twisted_rightwards_arrows", "two", "two_hearts", "two_hump_camel", "two_men_holding_hands", "two_oclock", "two_thirty", "two_women_holding_hands", "u5272", "u5408", "u55b6", "u6307", "u6708", "u6709", "u6e80", "u7121", "u7533", "u7981", "u7a7a", "uk", "umbrella", "umbrella_on_ground", "umbrella_with_rain_drops", "unamused", "unamused_face", "underage", "unicorn_face", "unlock", "up", "up_arrow", "up_button", "upside_down_face", "us", "v", "vertical_traffic_light", "vhs", "vibration_mode", "victory_hand", "video_camera", "video_game", "videocassette", "violin", "virgo", "volcano", "volleyball", "vs", "vulcan_salute", "walking", "waning_crescent_moon", "waning_gibbous_moon", "warning", "wastebasket", "watch", "water_buffalo", "water_closet", "water_wave", "watermelon", "wave", "waving_black_flag", "waving_hand", "waving_white_flag", "wavy_dash", "waxing_crescent_moon", "waxing_gibbous_moon", "wc", "weary", "weary_cat_face", "weary_face", "wedding", "weight_lifter", "whale", "whale2", "wheelchair", "white_check_mark", "white_circle", "white_flower", "white_large_square", "white_medium_small_square", "white_medium_square", "white_medium_star", "white_small_square", "white_square_button", "wind_chime", "wind_face", "wine_glass", "wink", "winking_face", "wolf", "wolf_face", "woman", "womans_boot", "womans_clothes", "womans_hat", "womans_sandal", "women_partying", "womens", "womens_room", "world_map", "worried", "worried_face", "wrapped_present", "wrench", "writing_hand", "x", "yellow_heart", "yen", "yen_banknote", "yin_yang", "yum", "zap", "zero", "zipper_mouth_face", "zzz"];

var unicode_emoji_names = ["1f198", "1f3ed", "0034", "1f341", "1f3d7", "26f9", "1f32c", "1f314", "1f199", "1f6b2", "267b", "270c", "1f622", "1f4ad", "1f698", "1f618", "1f3a8", "1f3eb", "1f3ae", "1f45f", "1f624", "1f437", "1f6b2", "1f193", "1f69f", "1f564", "1f4a9", "1f335", "1f69d", "1f498", "1f373", "1f195", "262e", "1f33f", "1f63e", "1f499", "1f4af", "1f343", "1f3a2", "1f432", "1f6b8", "1f69a", "2195", "1f5fb", "1f51f", "1f637", "1f4b7", "1f621", "1f250", "1f697", "1f51d", "1f3e5", "1f534", "1f5fa", "1f51a", "1f6e5", "1f1ee", "260e", "1f573", "1f45d", "1f3ee", "1f535", "1f004", "2199", "1f3b2", "1f4cc", "1f21a", "1f42c", "1f303", "25fd", "1f61a", "1f30e", "1f51a", "23ea", "1f355", "1f4bc", "1f63c", "1f6c3", "1f371", "1f497", "1f387", "2728", "261d", "1f337", "1f5e3", "1f691", "2614", "1f3e2", "1f3ac", "1f606", "1f5fe", "1f3e4", "1f635", "1f47f", "1f458", "1f194", "1f3ee", "1f55d", "2615", "1f461", "1f519", "1f62e", "1f4c3", "1f3e6", "1f35e", "1f506", "1f447", "1f694", "2651", "1f356", "1f5fc", "1f55b", "1f3a3", "1f44e", "1f51e", "1f52d", "1f915", "1f577", "1f21a", "1f4f8", "1f360", "1f50f", "1f1f7", "1f62f", "1f6c4", "1f338", "2747", "1f4a6", "1f449", "1f3b7", "1f3a3", "1f3b4", "1f423", "1f193", "1f4a8", "1f684", "1f357", "1f347", "1f63c", "1f36d", "25fe", "1f3e7", "1f4d4", "1f44d", "1f49d", "2702", "1f3b0", "1f3c0", "1f51d", "1f561", "1f6e4", "1f485", "1f38c", "1f606", "271d", "1f690", "1f6bf", "1f3bc", "1f415", "1f50a", "1f54b", "1f3c3", "1f6f3", "270d", "1f400", "1f391", "1f30c", "1f454", "1f63d", "2744", "1f58c", "1f52e", "1f201", "1f444", "2611", "1f55a", "24c2", "1f415", "1f5fe", "1f44e", "1f34d", "1f631", "1f4a3", "1f4e1", "1f4fb", "1f984", "1f237", "1f17f", "1f498", "1f31a", "1f192", "1f35a", "1f42f", "1f576", "1f22f", "1f1e9", "231a", "1f626", "1f349", "1f492", "1f232", "1f49d", "1f52c", "2049", "1f479", "1f473", "262a", "1f309", "1f6ad", "1f528", "1f61b", "1f4ee", "24c2", "1f6be", "2652", "1f629", "1f340", "1f55c", "1f37e", "1f404", "2755", "2b1c", "1f61a", "1f43d", "26f8", "1f643", "1f329", "1f624", "1f37a", "1f3df", "1f6eb", "1f436", "2797", "1f503", "1f344", "23fa", "1f644", "1f41c", "1f605", "1f390", "1f4fd", "2693", "0037", "1f363", "1f5c3", "1f46b", "1f4ab", "25b6", "1f3bb", "1f401", "1f194", "23eb", "1f49f", "1f313", "1f570", "1f6f0", "270b", "1f384", "1f381", "1f494", "1f61d", "1f30a", "2665", "1f614", "26c4", "2b06", "1f4b4", "1f4cf", "1f33e", "1f62a", "1f34f", "1f4c8", "25fb", "1f33b", "1f642", "1f61f", "1f629", "1f607", "1f639", "1f54e", "1f33d", "262f", "1f325", "1f55c", "1f6ec", "1f4c6", "1f381", "1f4ff", "1f61b", "1f50e", "1f4a9", "1f4ed", "1f451", "1f617", "1f496", "2663", "1f46e", "1f646", "1f64e", "1f32b", "1f361", "1f536", "1f197", "261d", "1f33d", "2733", "1f3c6", "1f4b0", "1f55f", "25aa", "2b55", "1f515", "1f35b", "1f62d", "1f312", "1f405", "0032", "1f198", "1f51c", "1f5dc", "2716", "1f3be", "1f493", "1f386", "1f632", "1f4f2", "3297", "1f647", "2754", "2196", "1f619", "23eb", "1f6a9", "1f34e", "1f604", "264a", "1f6a2", "1f4a9", "1f3a5", "1f505", "1f196", "1f332", "1f3c8", "2649", "1f69b", "1f51b", "1f693", "1f50f", "1f633", "2660", "1f636", "1f4fc", "1f377", "1f563", "1f608", "1f3bf", "1f3ec", "1f40a", "1f533", "27b0", "1f6a0", "1f348", "1f623", "1f531", "1f233", "1f6e0", "1f192", "1f506", "1f913", "1f333", "1f4ae", "00ae", "1f52b", "1f68f", "1f500", "1f55e", "2b05", "1f5dd", "1f538", "25ab", "1f52a", "1f5c2", "1f4c1", "1f522", "1f608", "1f3fa", "1f366", "26be", "1f466", "1f64c", "2795", "1f647", "1f688", "1f486", "1f239", "1f6a8", "1f4e4", "1f55e", "1f376", "1f616", "1f620", "1f4f6", "1f38d", "1f319", "1f605", "2648", "1f33e", "1f401", "1f47c", "1f482", "2709", "1f4b8", "1f37b", "1f645", "1f620", "1f399", "1f4a5", "1f697", "1f408", "0033", "1f3bd", "26f4", "2764", "1f4c8", "1f49a", "1f615", "1f475", "264f", "26f5", "1f4ec", "1f418", "1f4d6", "1f625", "1f238", "1f6e3", "1f31e", "1f382", "1f50d", "1f4c5", "1f54a", "1f468", "1f419", "267f", "1f69a", "1f202", "1f6e1", "1f487", "1f561", "2b07", "1f31c", "1f3f5", "1f4b1", "1f4ed", "1f5de", "23f3", "1f6c0", "1f42d", "1f564", "1f3b3", "1f422", "1f6af", "1f477", "1f911", "1f3bd", "1f513", "1f41e", "1f472", "1f3cb", "1f1ea", "2757", "1f30a", "1f17e", "1f3ce", "1f642", "1f486", "1f4d8", "1f397", "1f62c", "1f509", "1f171", "1f3b5", "1f460", "1f4d7", "1f3a7", "1f47e", "23f9", "270a", "1f48b", "1f60b", "1f63a", "26ce", "1f49e", "0031", "1f48d", "26a1", "1f411", "1f516", "267b", "1f578", "1f440", "1f4f1", "1f3f3", "1f4dd", "1f4a6", "1f595", "1f4fa", "1f53d", "1f332", "1f43e", "1f640", "1f562", "23f3", "1f3a9", "1f567", "1f69c", "1f236", "1f237", "1f63f", "1f47c", "1f17f", "1f4a8", "1f42e", "1f481", "1f4a2", "1f4ec", "270f", "1f50d", "1f609", "1f306", "1f321", "1f5a8", "1f32a", "1f392", "1f607", "1f63b", "1f4b3", "1f3c1", "1f4df", "1f364", "1f307", "26ab", "1f575", "1f6b6", "1f537", "1f45e", "1f306", "1f6cd", "2b06", "1f328", "1f4b9", "1f48e", "274e", "1f467", "1f602", "1f4e7", "1f234", "1f61f", "1f0cf", "274e", "1f4b5", "1f4aa", "1f462", "1f649", "1f3ea", "1f4ba", "1f6af", "2653", "1f4c5", "1f625", "1f4e2", "1f60d", "1f3d5", "1f6b4", "1f3f7", "2666", "1f64b", "26bd", "1f1ec", "1f336", "1f1ef", "1f603", "1f3b8", "1f326", "1f372", "1f379", "1f502", "1f6bb", "1f320", "1f42c", "23e9", "264b", "1f456", "1f52a", "1f417", "26f5", "1f983", "1f471", "1f430", "1f685", "1f61d", "1f681", "1f39b", "1f3ad", "1f405", "1f63d", "1f301", "1f509", "1f421", "1f4ac", "1f331", "1f4e9", "1f3c8", "2b1b", "1f234", "1f4f0", "1f236", "1f41a", "1f45b", "260e", "1f634", "1f433", "1f54d", "1f3d8", "1f639", "1f6b5", "1f686", "1f6ce", "1f4a0", "1f3c3", "1f488", "1f368", "1f523", "1f32f", "1f579", "1f695", "21aa", "1f238", "1f46f", "1f42b", "1f3c2", "1f339", "23f1", "1f48a", "26f7", "1f4d9", "1f3af", "1f61e", "1f601", "1f6d0", "1f47a", "1f504", "1f567", "1f606", "1f488", "1f44f", "2194", "1f3ef", "1f63b", "1f371", "1f314", "1f38b", "1f17e", "1f52a", "1f30b", "1f618", "1f51b", "1f549", "1f197", "1f307", "1f4e6", "27a1", "1f4c9", "1f43a", "1f402", "1f5e1", "1f550", "1f910", "1f489", "1f362", "1f391", "1f382", "2705", "1f613", "1f320", "1f3c1", "1f518", "2935", "1f621", "1f40b", "269b", "1f4fc", "1f353", "1f6b1", "1f31f", "1f638", "1f6bd", "1f18e", "1f202", "1f3a6", "1f170", "1f191", "1f4be", "1f455", "1f4de", "1f614", "1f32d", "1f64f", "1f565", "1f633", "1f4a9", "203c", "1f350", "1f6e2", "1f637", "1f60f", "1f304", "26c5", "1f58b", "1f4b5", "1f4a1", "1f6b3", "1f472", "1f4fa", "1f450", "1f6a8", "303d", "2122", "1f604", "1f535", "1f4e0", "1f469", "1f3ab", "1f35c", "1f500", "1f378", "1f5ef", "1f44e", "1f682", "1f327", "1f641", "1f375", "0030", "1f380", "1f524", "1f49c", "1f44d", "1f530", "0023", "1f631", "1f64e", "1f3c4", "1f68f", "1f311", "26a1", "1f44d", "1f61c", "26d4", "1f4db", "1f3db", "1f439", "26cf", "269c", "1f46a", "1f358", "1f4e5", "23ed", "1f62b", "1f3a0", "1f441", "1f429", "25c0", "1f4e3", "1f330", "1f6aa", "1f324", "1f4ea", "1f6b9", "1f383", "1f3da", "0039", "1f36b", "270c", "1f354", "1f251", "1f4a1", "1f60c", "2708", "1f457", "1f6a4", "26c4", "1f4d2", "1f410", "23f8", "1f1eb", "1f51c", "1f531", "1f374", "23e9", "1f404", "1f53b", "1f170", "1f3d0", "1f409", "1f527", "1f446", "1f373", "1f53a", "1f5b1", "1f64f", "1f3c9", "1f557", "26bd", "23ef", "1f38e", "1f435", "1f4ca", "1f3f0", "1f396", "1f60f", "1f5e8", "1f359", "1f68e", "1f475", "1f3ee", "2139", "1f4ef", "1f3e0", "1f41f", "1f470", "270a", "1f628", "1f484", "26f2", "1f300", "1f4a0", "1f6a5", "1f501", "1f36a", "1f632", "1f611", "1f493", "1f3f0", "1f60a", "1f19a", "1f3c5", "1f692", "1f43e", "1f40e", "1f5ff", "1f33c", "1f697", "1f689", "1f562", "1f455", "1f34c", "1f60c", "1f3e8", "1f559", "1f6a1", "1f43c", "1f171", "1f18e", "1f52f", "1f367", "1f43f", "1f6b6", "1f626", "26f0", "1f428", "1f52f", "1f425", "1f23a", "1f310", "1f3e0", "1f439", "1f4b9", "1f201", "1f3ac", "1f45e", "1f1f0", "26e9", "1f250", "26f3", "1f4bd", "1f58d", "1f447", "1f30e", "00a9", "1f465", "1f3a9", "1f485", "23f0", "1f48f", "1f3aa", "2600", "1f4e8", "1f552", "1f49b", "1f622", "1f4b4", "1f35b", "1f50a", "274c", "1f62e", "1f563", "1f53c", "1f3a8", "1f389", "1f393", "1f553", "1f33a", "1f0cf", "270b", "1f636", "1f39f", "1f43b", "1f6ab", "1f474", "1f5ff", "1f3f4", "1f4eb", "1f5fd", "1f4e3", "1f6c0", "1f346", "1f370", "1f43a", "1f514", "1f50b", "1f5d1", "1f483", "1f4c4", "26ea", "1f515", "1f51e", "3299", "1f55f", "1f4eb", "1f40f", "1f232", "1f4b7", "1f525", "1f630", "1f60d", "1f30d", "21aa", "1f35f", "1f302", "1f459", "1f6a6", "1f617", "27bf", "1f590", "1f46d", "1f4b2", "1f5d3", "26d1", "1f455", "1f554", "27a1", "1f6c5", "1f41d", "1f448", "1f513", "1f37d", "2934", "1f40c", "1f53d", "1f406", "1f566", "1f3d9", "1f555", "1f4b6", "1f37b", "1f638", "1f4d0", "1f551", "1f552", "1f38f", "1f553", "1f60e", "1f3e9", "1f64a", "1f453", "27bf", "1f558", "1f42a", "1f452", "1f461", "1f38f", "1f352", "1f315", "1f4c9", "1f46b", "1f5f3", "1f45a", "203c", "1f61c", "1f38d", "1f004", "1f474", "1f699", "1f316", "1f519", "1f444", "1f56f", "1f916", "1f58a", "23ee", "2796", "1f443", "1f44a", "1f4a4", "1f3b6", "1f372", "1f385", "1f4a2", "1f420", "1f507", "1f3d1", "1f251", "1f392", "1f3e2", "1f44a", "1f6ba", "1f6bc", "1f424", "1f6b1", "1f317", "1f389", "1f560", "2753", "1f6a9", "1f560", "1f565", "1f4f1", "263a", "1f39a", "1f517", "1f427", "1f50c", "1f480", "1f35f", "1f199", "1f1fa", "1f45f", "1f615", "1f4b6", "1f425", "2712", "26a0", "1f3f9", "1f308", "1f34b", "1f351", "1f682", "1f53a", "1f68d", "1f522", "1f603", "1f235", "25fc", "1f4d5", "1f3dc", "1f611", "1f4c0", "1f50e", "23ea", "1f3dd", "1f4dc", "1f407", "1f60b", "1f3e4", "1f6be", "1f47d", "1f31b", "1f1ec", "1f38e", "1f3cc", "1f627", "1f54c", "2734", "1f44b", "1f6e9", "1f504", "1f683", "1f3b6", "1f645", "1f6ae", "1f5b2", "1f35d", "1f233", "1f48c", "1f4cb", "1f37c", "1f426", "1f6cb", "1f521", "1f4c7", "1f44a", "264c", "1f3e1", "1f648", "1f687", "1f37f", "1f375", "2b55", "263a", "1f34e", "1f60a", "1f55d", "1f6b9", "2601", "1f36f", "1f438", "1f4f7", "1f980", "1f4f9", "1f634", "270f", "1f6b5", "1f34a", "1f6ba", "1f686", "1f403", "1f476", "1f334", "21a9", "1f62a", "1f520", "1f6ae", "26b0", "1f521", "1f512", "1f416", "1f3ba", "1f431", "1f55b", "0036", "21a9", "1f30f", "2714", "1f448", "1f4d3", "1f32e", "1f345", "1f507", "26b1", "1f523", "1f3cd", "1f623", "1f4ce", "1f4b0", "1f31d", "1f610", "1f31f", "1f4f6", "1f40d", "1f48f", "1f699", "1f38a", "1f37a", "2b50", "1f4bf", "1f68a", "1f524", "1f502", "1f63a", "1f453", "1f530", "1f4f4", "1f4da", "1f64c", "1f3b1", "1f4af", "1f378", "1f35c", "2614", "1f35a", "1f478", "1f235", "1f6c2", "1f539", "1f48e", "1f490", "1f365", "1f551", "1f62d", "1f3de", "1f412", "1f510", "1f914", "1f627", "1f41a", "1f53b", "1f529", "1f47a", "1f3af", "1f612", "26fd", "1f6cf", "1f41d", "1f4cd", "1f4d1", "1f68b", "1f3a4", "25b6", "1f3b1", "1f446", "231b", "1f449", "0038", "1f3e3", "1f45c", "1f503", "1f63e", "1f62c", "1f31a", "2757", "1f195", "1f3c7", "1f414", "26f1", "2198", "1f982", "1f318", "264d", "264e", "1f61e", "2650", "1f616", "1f6a5", "1f43b", "1f4f5", "1f46f", "1f4f2", "1f696", "1f479", "1f4bb", "2b07", "1f3a1", "1f601", "23ec", "1f408", "26c8", "1f366", "1f30f", "274c", "1f52b", "2709", "1f9c0", "26fa", "1f602", "1f5c4", "1f511", "1f491", "1f505", "1f385", "1f646", "1f47e", "1f1e8", "1f191", "1f30d", "1f4bf", "1f360", "1f3ca", "3030", "1f684", "1f46e", "1f495", "1f6ac", "1f4c2", "1f628", "1f600", "2b05", "1f6c1", "1f3d3", "23f2", "1f41e", "1f239", "1f413", "1f19a", "1f596", "1f5bc", "1f685", "26aa", "1f196", "1f388", "1f343", "1f508", "1f6cc", "1f22f", "23ec", "1f40b", "1f62f", "1f612", "1f497", "1f3f8", "1f4aa", "1f5d2", "1f680", "1f42a", "1f462", "26f3", "1f526", "1f460", "1f5a5", "1f3bf", "1f3b9", "1f4a5", "1f6b0", "26c5", "1f550", "1f912", "1f917", "0035", "1f554", "1f555", "1f556", "1f557", "1f558", "1f369", "1f3e7", "1f587", "1f36c", "1f46c", "2668", "1f23a", "1f4e0", "1f464", "1f4e7", "26d3", "1f918", "1f619", "1f365", "1f6ab", "1f6b7", "25c0", "1f4ea", "1f39e", "1f559", "1f55a", "1f613", "1f69e", "1f445", "1f532", "1f3a7", "1f630", "1f4bb", "1f44c", "1f36e", "1f6a3", "26fd", "1f609", "1f44f", "1f981", "1f3cf", "1f68c", "1f6a7", "1f342", "1f438", "1f442", "1f41b", "1f64b", "1f3d4", "1f556", "23cf", "1f370", "1f393", "1f44b", "1f416", "1f520", "1f3d2", "1f64d", "1f434", "2197", "1f4d6", "1f566", "1f305", "1f40e", "1f3d6", "1f501", "2b50", "1f407", "1f463", "1f47b", "1f4a7", "1f4f3", "1f640", "1f600", "1f574"];

emoji_names.push("zulip");

_.each(emoji_names, function (value) {
    default_emojis.push({emoji_name: value, emoji_url: "/static/third/gemoji/images/emoji/" + value + ".png"});
});

_.each(unicode_emoji_names, function (value) {
    default_unicode_emojis.push({emoji_name: value, emoji_url: "/static/third/gemoji/images/emoji/unicode/" + value + ".png"});
});

exports.update_emojis = function update_emojis(realm_emojis) {
    // Copy the default emoji list and add realm-specific emoji to it
    exports.emojis = default_emojis.slice(0);
    _.each(realm_emojis, function (data, name) {
        exports.emojis.push({emoji_name:name, emoji_url: data.display_url});
    });
    exports.emojis_by_name = {};
    _.each(exports.emojis, function (emoji) {
        exports.emojis_by_name[emoji.emoji_name] = emoji.emoji_url;
    });
    exports.emojis_by_unicode = {};
    _.each(default_unicode_emojis, function (emoji) {
        exports.emojis_by_unicode[emoji.emoji_name] = emoji.emoji_url;
    });
};

exports.update_emojis(page_params.realm_emoji);

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = emoji;
}
