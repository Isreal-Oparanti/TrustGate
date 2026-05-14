"""Download optional NLP assets used by the TrustGate NLP demo."""

import nltk


def main() -> None:
    for package in [
        "punkt",
        "punkt_tab",
        "stopwords",
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
        "wordnet",
    ]:
        nltk.download(package)

    print("NLTK assets installed.")
    print("Optional spaCy model command:")
    print("python -m spacy download en_core_web_sm")


if __name__ == "__main__":
    main()
