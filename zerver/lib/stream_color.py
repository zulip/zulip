STREAM_ASSIGNMENT_COLORS = [
    "#76ce90",
    "#fae589",
    "#a6c7e5",
    "#e79ab5",
    "#bfd56f",
    "#f4ae55",
    "#b0a5fd",
    "#addfe5",
    "#f5ce6e",
    "#c2726a",
    "#94c849",
    "#bd86e5",
    "#ee7e4a",
    "#a6dcbf",
    "#95a5fd",
    "#53a063",
    "#9987e1",
    "#e4523d",
    "#c2c2c2",
    "#4f8de4",
    "#c6a8ad",
    "#e7cc4d",
    "#c8bebf",
    "#a47462",
]


def pick_colors(
    used_colors: set[str], color_map: dict[int, str], recipient_ids: list[int]
) -> dict[int, str]:
    used_colors = set(used_colors)
    recipient_ids = sorted(recipient_ids)
    result = {}

    other_recipient_ids = []
    for recipient_id in recipient_ids:
        if recipient_id in color_map:
            color = color_map[recipient_id]
            result[recipient_id] = color
            used_colors.add(color)
        else:
            other_recipient_ids.append(recipient_id)

    available_colors = [s for s in STREAM_ASSIGNMENT_COLORS if s not in used_colors]

    for i, recipient_id in enumerate(other_recipient_ids):
        if i < len(available_colors):
            color = available_colors[i]
        else:
            # We have to start reusing old colors, and we use recipient_id
            # to choose the color.
            color = STREAM_ASSIGNMENT_COLORS[recipient_id % len(STREAM_ASSIGNMENT_COLORS)]
        result[recipient_id] = color

    return result
