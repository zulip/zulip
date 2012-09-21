subs_lists = {}
subs_lists['default'] = """\
""".split()

all_subs = set()
for sub_list in subs_lists.values():
    for sub in sub_list:
        all_subs.add(sub)
