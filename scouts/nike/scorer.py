from brain.atlas_brain import AtlasBrain


def score_nike_item(item):
    return AtlasBrain.analyze(
        item=item,
        category="nike",
    )