from memory.nike_memory import nike_memory


def detect_patterns():
    memory = nike_memory()

    observations = []

    if memory["total_items_seen"] >= 3:
        observations.append(
            "Nike activity is repeating. Atlas has observed multiple Nike opportunities."
        )

    if memory["hype_drop_count"] >= 2:
        observations.append(
            "Hype-drop behavior is increasing. Multiple Nike launches contain high-demand signals."
        )

    if memory["restock_count"] >= 1:
        observations.append(
            "Nike restock language has appeared. Atlas treats restocks as watch signals, not automatic buys."
        )

    if memory["collab_count"] >= 1:
        observations.append(
            "Collaboration signals are present. Nike collaborations often attract strong resale attention."
        )

    return observations