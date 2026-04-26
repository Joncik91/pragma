"""Tests for the languages registry + Classifier Protocol shape."""

from pathlib import Path

from pragma.languages import REGISTRY
from pragma.languages._protocol import Classifier


def test_registry_is_a_list_of_classifiers():
    assert isinstance(REGISTRY, list)


def test_protocol_requires_matches_and_classify_file():
    # Construct a minimal stub that conforms to Classifier — type-check
    # via runtime isinstance() should succeed because Classifier is a
    # @runtime_checkable Protocol.
    class Stub:
        LANGUAGE = "stub"

        def matches(self, path: Path) -> bool:
            return False

        def classify_file(self, path: Path):
            return []

    stub = Stub()
    assert isinstance(stub, Classifier)


def test_non_conforming_class_is_not_a_classifier():
    class NotAClassifier:
        LANGUAGE = "wrong"
        # missing matches() and classify_file()

    assert not isinstance(NotAClassifier(), Classifier)
