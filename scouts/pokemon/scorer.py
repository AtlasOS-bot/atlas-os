from brain.atlas_brain import AtlasBrain


def score_pokemon_item(item):
    return AtlasBrain.analyze(
        item=item,
        category="pokemon",
    )