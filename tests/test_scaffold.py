"""Scaffold tests: importability and pin integrity — no network, no R."""

import re

import define_uk


def test_version():
    assert define_uk.__version__


def test_pin_is_a_full_sha():
    assert re.fullmatch(r"[0-9a-f]{40}", define_uk.UPSTREAM_COMMIT)


def test_upstream_url_is_the_unlicensed_source_we_do_not_vendor():
    assert define_uk.UPSTREAM_URL.startswith(
        "https://github.com/DEFINE-model/"
    )
