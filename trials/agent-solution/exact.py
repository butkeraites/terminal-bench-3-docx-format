"""Exact rational arithmetic helpers for certificate verification.

Everything here works on integers only.  A rational is carried as a pair
``(num, den)`` with ``den > 0`` and ``gcd(num, den) == 1``; a vector of
rationals is carried as a list of integers scaled by one common positive
denominator.  No floating point value is ever produced, so every comparison
the verifier makes is exact.
"""

from __future__ import annotations

import math
import re
from itertools import chain

import numpy as np

# --------------------------------------------------------------------------
# wire value parsing
# --------------------------------------------------------------------------

# Integers, decimals and scientific notation.  Written with explicit [0-9] so
# that non-ASCII digits (which ``int``/``float`` would happily accept) are
# rejected, and anchored so that whitespace, underscores, "nan" and "inf" are
# rejected too.
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_FRACTION = re.compile(r"([+-]?[0-9]+)/([+-]?[0-9]+)")

# A ludicrous exponent would only ever be a denial-of-service attempt; refuse
# to materialise the integer.
_MAX_EXPONENT = 100_000


def parse_value(text):
    """Parse one wire value into ``(num, den)``; return ``None`` if malformed."""
    if type(text) is not str:
        return None

    if "/" in text:
        matched = _FRACTION.fullmatch(text)
        if matched is None:
            return None
        num = int(matched.group(1))
        den = int(matched.group(2))
        if den == 0:
            return None
        if den < 0:
            num, den = -num, -den
        common = math.gcd(num, den)
        if common > 1:
            num //= common
            den //= common
        return num, den

    if _DECIMAL.fullmatch(text) is None:
        return None

    exponent = 0
    mantissa = text
    marker = text.find("e")
    if marker < 0:
        marker = text.find("E")
    if marker >= 0:
        exponent = int(text[marker + 1 :])
        if exponent > _MAX_EXPONENT or exponent < -_MAX_EXPONENT:
            return None
        mantissa = text[:marker]

    point = mantissa.find(".")
    if point >= 0:
        fraction = mantissa[point + 1 :]
        mantissa = mantissa[:point] + fraction
        exponent -= len(fraction)

    num = int(mantissa)
    if exponent >= 0:
        return num * 10**exponent, 1

    den = 10 ** (-exponent)
    common = math.gcd(num, den)
    if common > 1:
        num //= common
        den //= common
    return num, den


# --------------------------------------------------------------------------
# value cache
#
# A single graded stream repeats the same few thousand distinct wire values
# tens of thousands of times each, so parsing is memoised.  ``_INDEX`` maps a
# wire string to a slot in the tables below; slot 0 is reserved for malformed
# values, which lets "is anything malformed?" become one vectorised test.
# --------------------------------------------------------------------------

_INT64_MAX = (1 << 63) - 1

_NUMER: list[int] = [0]
_DENOM: list[int] = [0]
# Mirrors of the two tables above with anything that does not fit in an int64
# replaced by the sentinel ``den == -1``.
_NUMER_SMALL: list[int] = [0]
_DENOM_SMALL: list[int] = [0]

_CACHE_LIMIT = 300_000


class _ValueIndex(dict):
    """``dict`` that parses and interns wire values on first sight."""

    __slots__ = ()

    def __missing__(self, key):
        parsed = parse_value(key)
        if parsed is None:
            slot = 0
        else:
            num, den = parsed
            slot = len(_NUMER)
            _NUMER.append(num)
            _DENOM.append(den)
            if -_INT64_MAX <= num <= _INT64_MAX and den <= _INT64_MAX:
                _NUMER_SMALL.append(num)
                _DENOM_SMALL.append(den)
            else:
                _NUMER_SMALL.append(0)
                _DENOM_SMALL.append(-1)
        self[key] = slot
        return slot


_INDEX = _ValueIndex()

_numer_np = np.array(_NUMER_SMALL, dtype=np.int64)
_denom_np = np.array(_DENOM_SMALL, dtype=np.int64)


def _sync_tables():
    global _numer_np, _denom_np
    if len(_NUMER_SMALL) != _numer_np.shape[0]:
        _numer_np = np.array(_NUMER_SMALL, dtype=np.int64)
        _denom_np = np.array(_DENOM_SMALL, dtype=np.int64)


def maybe_trim_cache():
    """Bound cache growth.  Only safe to call between requests."""
    if len(_INDEX) > _CACHE_LIMIT:
        _INDEX.clear()
        del _NUMER[1:], _DENOM[1:], _NUMER_SMALL[1:], _DENOM_SMALL[1:]
        _sync_tables()


def cache_values(texts):
    """Pre-intern a batch of wire values."""
    lookup = _INDEX.__getitem__
    for text in texts:
        lookup(text)
    _sync_tables()


class Malformed(Exception):
    """A wire value did not match any accepted numeric form."""


def parse_vector(texts):
    """Parse a list of wire values into ``(numerators, denominators)``."""
    lookup = _INDEX.__getitem__
    numerators = []
    denominators = []
    append_n = numerators.append
    append_d = denominators.append
    for text in texts:
        try:
            slot = lookup(text)
        except TypeError:  # unhashable, therefore not a wire value
            raise Malformed from None
        if slot == 0:
            raise Malformed
        append_n(_NUMER[slot])
        append_d(_DENOM[slot])
    return numerators, denominators


def parse_scalar(text):
    """Parse a single wire value into ``(num, den)``."""
    try:
        slot = _INDEX[text]
    except TypeError:
        raise Malformed from None
    if slot == 0:
        raise Malformed
    return _NUMER[slot], _DENOM[slot]


def common_scale(numerators, denominators):
    """Scale a rational vector onto one common denominator.

    Returns ``(scaled, denom)`` with ``scaled[j] / denom == num[j] / den[j]``.
    """
    denom = math.lcm(*denominators) if denominators else 1
    if denom == 1:
        return list(numerators), 1
    return [n * (denom // d) for n, d in zip(numerators, denominators)], denom


# --------------------------------------------------------------------------
# the constraint matrix
#
# ``A`` is by far the largest object in a submission (n * m entries), so it
# gets a vectorised path: parse to int64 numerator/denominator arrays, scale
# onto one common denominator, then split into unsigned limbs so that the two
# matrix-vector products can run as exact int64 numpy matmuls.
# --------------------------------------------------------------------------

_SCALE_CEILING = 1 << 61


class ScaledMatrix:
    """``A`` scaled by ``denom`` into an exact integer matrix."""

    __slots__ = ("denom", "rows", "limbs", "limb_bits", "shape")

    def __init__(self, denom, shape, rows=None, limbs=None, limb_bits=0):
        self.denom = denom
        self.shape = shape
        self.rows = rows
        self.limbs = limbs
        self.limb_bits = limb_bits


def _limb_count(magnitude, limb_bits):
    """Number of limbs needed to hold every value with ``|v| <= magnitude``."""
    return max(1, -(-(magnitude.bit_length() + 1) // limb_bits))


def _split_int64(values, count, limb_bits):
    """Split a signed int64 array into ``count`` limbs, low limb first."""
    if count == 1:
        return [values]
    mask = (1 << limb_bits) - 1
    limbs = [(values >> (limb_bits * k)) & mask for k in range(count - 1)]
    limbs.append(values >> (limb_bits * (count - 1)))
    return limbs


def _split_python(values, count, limb_bits):
    """Split a list of Python ints into ``count`` int64 limb arrays."""
    size = len(values)
    if count == 1:
        return [np.array(values, dtype=np.int64)]
    mask = (1 << limb_bits) - 1
    limbs = []
    for k in range(count - 1):
        shift = limb_bits * k
        limbs.append(
            np.fromiter(((v >> shift) & mask for v in values), np.int64, size)
        )
    shift = limb_bits * (count - 1)
    limbs.append(np.fromiter((v >> shift for v in values), np.int64, size))
    return limbs


def choose_limb_bits(inner):
    """Largest limb width whose products still sum without overflowing int64.

    A limb product is below ``2 ** (2 * bits)`` and ``inner`` of them are
    accumulated per matmul, then a handful of matmuls are added together; the
    five bits of headroom below int64 cover that last step.
    """
    bits = (57 - max(inner, 1).bit_length()) // 2
    return max(1, min(24, bits))


def build_matrix(rows, m, n, limb_bits):
    """Parse and scale ``A``.  Raises :class:`Malformed` on a bad wire value."""
    total = m * n
    if total == 0:
        return ScaledMatrix(1, (m, n), rows=[[] for _ in range(m)])

    lookup = _INDEX.__getitem__
    try:
        slots = np.fromiter(map(lookup, chain.from_iterable(rows)), np.int64, total)
    except TypeError:
        raise Malformed from None
    _sync_tables()
    if not slots.all():
        raise Malformed

    numerators = _numer_np[slots]
    denominators = _denom_np[slots]

    if denominators.min() > 0:
        scale = 1
        for value in np.unique(denominators).tolist():
            scale = scale // math.gcd(scale, value) * value
            if scale > _INT64_MAX:
                break
        else:
            largest = int(np.abs(numerators).max()) * (
                scale // int(denominators.min())
            )
            if largest < _SCALE_CEILING:
                scaled = numerators * (scale // denominators)
                magnitude = int(np.abs(scaled).max())
                count = _limb_count(magnitude, limb_bits)
                limbs = _split_int64(scaled.reshape(m, n), count, limb_bits)
                return ScaledMatrix(
                    scale, (m, n), limbs=limbs, limb_bits=limb_bits
                )

    # Fallback: unbounded integers, one row at a time.
    slot_list = slots.tolist()
    numer = _NUMER
    denom = _DENOM
    flat_n = [numer[s] for s in slot_list]
    flat_d = [denom[s] for s in slot_list]
    scale = math.lcm(*set(flat_d))
    flat = [a * (scale // b) for a, b in zip(flat_n, flat_d)]
    return ScaledMatrix(
        scale, (m, n), rows=[flat[i * n : (i + 1) * n] for i in range(m)]
    )


def _combine(parts, shifts):
    if len(parts) == 1:
        return parts[0].tolist()
    columns = [part.tolist() for part in parts]
    return [
        sum(value << shift for value, shift in zip(values, shifts))
        for values in zip(*columns)
    ]


def matvec(matrix, vector):
    """Exact ``A_scaled @ vector`` -> list of Python ints (length m)."""
    m, n = matrix.shape
    if n == 0:
        return [0] * m
    if matrix.rows is not None:
        return [math.sumprod(row, vector) for row in matrix.rows]

    limb_bits = matrix.limb_bits
    magnitude = max(max(vector), -min(vector))
    count = _limb_count(magnitude, limb_bits)
    pieces = _split_python(vector, count, limb_bits)

    accumulator = {}
    for p, left in enumerate(matrix.limbs):
        for q, right in enumerate(pieces):
            product = left @ right
            key = p + q
            if key in accumulator:
                accumulator[key] += product
            else:
                accumulator[key] = product
    order = sorted(accumulator)
    return _combine(
        [accumulator[k] for k in order], [limb_bits * k for k in order]
    )


def vecmat(vector, matrix):
    """Exact ``vector @ A_scaled`` -> list of Python ints (length n)."""
    m, n = matrix.shape
    if m == 0:
        return [0] * n
    if matrix.rows is not None:
        return [math.sumprod(column, vector) for column in zip(*matrix.rows)]

    limb_bits = matrix.limb_bits
    magnitude = max(max(vector), -min(vector))
    count = _limb_count(magnitude, limb_bits)
    pieces = _split_python(vector, count, limb_bits)

    accumulator = {}
    for p, left in enumerate(matrix.limbs):
        for q, right in enumerate(pieces):
            product = right @ left
            key = p + q
            if key in accumulator:
                accumulator[key] += product
            else:
                accumulator[key] = product
    order = sorted(accumulator)
    return _combine(
        [accumulator[k] for k in order], [limb_bits * k for k in order]
    )
