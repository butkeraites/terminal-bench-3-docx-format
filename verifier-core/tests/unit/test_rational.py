"""Exact rational arithmetic — the ground truth the whole task is defined against.

Every quantity in an instance and a certificate arrives as a DECIMAL STRING and
is parsed exactly. This is deliberate: float("0.1") is not 1/10, so a verifier
that parses to float has already lost precision before it evaluates anything.
"""

from fractions import Fraction

import pytest

from certverify.domain.rational import (
    exact_dot,
    parse_rational,
    parse_vector,
    to_decimal_string,
)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def test_decimal_string_parses_exactly_not_through_float():
    """The headline trap: 0.1 has no exact binary representation."""
    assert parse_rational("0.1") == Fraction(1, 10)
    assert parse_rational("0.1") != Fraction(float("0.1"))


def test_integer_strings_parse():
    assert parse_rational("42") == Fraction(42)
    assert parse_rational("-7") == Fraction(-7)


def test_negative_and_zero_decimals():
    assert parse_rational("-0.25") == Fraction(-1, 4)
    assert parse_rational("0") == Fraction(0)
    assert parse_rational("-0.0") == Fraction(0)


def test_scientific_notation_parses_exactly():
    assert parse_rational("1e3") == Fraction(1000)
    assert parse_rational("1.5e-2") == Fraction(3, 200)


def test_explicit_fraction_syntax():
    """Some instances need values no finite decimal can express, e.g. 1/3."""
    assert parse_rational("1/3") == Fraction(1, 3)
    assert parse_rational("-2/6") == Fraction(-1, 3)


def test_bare_float_input_is_rejected():
    """Accepting a Python float would silently import its rounding error."""
    with pytest.raises(TypeError):
        parse_rational(0.1)  # type: ignore[arg-type]


def test_malformed_input_is_rejected():
    for bad in ("", "abc", "1.2.3", "1/0", "--1", "1/"):
        with pytest.raises((ValueError, ZeroDivisionError)):
            parse_rational(bad)


def test_parse_vector_maps_elementwise():
    assert parse_vector(["0.1", "2", "-1/4"]) == [
        Fraction(1, 10),
        Fraction(2),
        Fraction(-1, 4),
    ]


# --------------------------------------------------------------------------
# exact_dot — where float implementations disagree with each other
# --------------------------------------------------------------------------


def test_exact_dot_of_small_vectors():
    a = parse_vector(["1", "2", "3"])
    b = parse_vector(["4", "5", "6"])
    assert exact_dot(a, b) == Fraction(32)


def test_exact_dot_is_immune_to_catastrophic_cancellation():
    """numpy.dot returns 1.0 here and naive float summation returns 2.0.

    Both are 'reasonable' float implementations and they disagree, which is
    exactly why the specification is written against exact arithmetic.
    """
    c = parse_vector(["1e16", "1", "-1e16", "1"])
    x = parse_vector(["1", "1", "1", "1"])

    assert exact_dot(c, x) == Fraction(2)


def test_exact_dot_accumulates_tenths_without_drift():
    """Three tenths is exactly 3/10; float summation gives 0.30000000000000004.

    (Ten tenths happens to round back to exactly 1.0, so it is the wrong
    example to make this point with.)
    """
    a = parse_vector(["0.1"] * 3)
    b = parse_vector(["1"] * 3)

    assert exact_dot(a, b) == Fraction(3, 10)
    assert sum([0.1] * 3) != 0.3


def test_exact_dot_rejects_length_mismatch():
    with pytest.raises(ValueError):
        exact_dot(parse_vector(["1", "2"]), parse_vector(["1"]))


def test_exact_dot_of_empty_vectors_is_zero():
    assert exact_dot([], []) == Fraction(0)


# --------------------------------------------------------------------------
# serialisation back out
# --------------------------------------------------------------------------


def test_round_trip_through_decimal_string():
    for s in ("0.1", "-0.25", "42", "0"):
        assert parse_rational(to_decimal_string(parse_rational(s))) == parse_rational(s)


def test_non_terminating_rational_serialises_as_a_fraction():
    """1/3 has no finite decimal expansion, so it must keep fraction syntax."""
    assert parse_rational(to_decimal_string(Fraction(1, 3))) == Fraction(1, 3)
