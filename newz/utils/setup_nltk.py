import nltk
from pathlib import Path

root = Path(__file__).parent

REQUIRED_CORPORA = [
    'brown',  # Required for FastNPExtractor
    'punkt',  # Required for WordTokenizer
    'maxent_treebank_pos_tagger',  # Required for NLTKTagger
    'movie_reviews',  # Required for NaiveBayesAnalyzer
    'wordnet',  # Required for lemmatization and Wordnet
    'stopwords'
]

complete_file = root.joinpath('.nltk_complete')
if not complete_file.exists():
    for each in REQUIRED_CORPORA:
        try:
            nltk.data.find(each)
        except LookupError:
            nltk.download(each)
    complete_file.touch()