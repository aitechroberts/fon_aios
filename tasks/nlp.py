def embed(text: str):
    # returns list[float]
    return [0.0] * 1536

def ner(text: str):
    class Ent:  # minimal placeholder
        def __init__(self, text):
            self.text = text
    return [Ent("DARPA")]

def coref(text: str):
    return {}

def relations(text: str, ents, coref_out):
    return []