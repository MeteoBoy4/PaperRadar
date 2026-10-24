"""数值规则 v1:封闭记法比较,不换算单位或拼接来源。"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from paper_radar.reading.context import SourceSlice
from paper_radar.reading.diagnostics import NumericReason as NumericReason

NUMERIC_RULE_VERSION = "read-numeric-v1"


# 单位别名及其大小写是封闭记法;未知相邻词不参与比较。
UNIT_ALIASES = (
    ("m s⁻¹", "m/s"),
    ("m s-1", "m/s"),
    ("m/s", "m/s"),
    ("米/秒", "m/s"),
    ("hPa", "hPa"),
    ("百帕", "hPa"),
    ("km", "km"),
    ("公里", "km"),
    ("千米", "km"),
    ("°C", "°C"),
    ("摄氏度", "°C"),
    ("%", "%"),
    ("m", "m"),
    ("米", "m"),
)
_FULLWIDTH = str.maketrans("０１２３４５６７８９＋－．，％−", "0123456789+-.,%-")
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_SCIENTIFIC = re.compile(
    r"(?<![A-Za-z0-9.])(?P<mant>(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))"
    r"\s*[×x]\s*10(?P<exponent>[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+|\^[+-]?[0-9]+)"
    r"(?![0-9⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]|\.[0-9])"
)
_POWER = re.compile(
    r"(?<![A-Za-z0-9.])10(?P<exponent>[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+|\^[+-]?[0-9]+)"
    r"(?![0-9⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]|\.[0-9])"
)
_UNSUPPORTED_FORM = re.compile(
    r"(?<![A-Za-z0-9.])(?:"
    r"(?:[0-9]+(?:\.[0-9]+)?)\s*[×x]\s*10"
    r"(?:\^[^\s,;。，；]*|[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+[0-9.]*)?"
    r"|(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
    r"(?:\^[^\s,;。，；]*|[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+[0-9.]*)"
    r"|[0-9]+/[0-9]+)"
)
_ATOM = re.compile(r"[+\-±]?(?:[0-9][0-9,.]*|\.[0-9]+)(?:[eE][+\-]?[0-9]*)?")
_VALID_NUMBER = re.compile(
    r"[+\-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?(?:[eE][+\-]?[0-9]+)?|[+\-]?\.[0-9]+(?:[eE][+\-]?[0-9]+)?"
)
_REFERENCE_PREFIX = re.compile(
    r"(?:图|表|式|节|(?<![A-Za-z0-9])(?:Fig\.|Figure|Table|Eq\.|Section))"
    r"\s*[\(\[]?\s*$",
    re.IGNORECASE,
)
_RANGE = re.compile(r"\s*(?:–|~|～|至|to|-)\s*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Atom:
    value: Decimal | None = field(repr=False)
    uncertainty: bool
    unit: str | None
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NumericLiteral:
    text: str = field(repr=False)
    values: tuple[Decimal | None, ...] = field(repr=False)
    uncertainty: tuple[bool, ...]
    units: tuple[str | None, ...]

    @property
    def unit(self) -> str | None:
        return self.units[-1]

    @property
    def recognized(self) -> bool:
        return all(value is not None for value in self.values)


@dataclass(frozen=True, slots=True)
class NumericMatch:
    literal: NumericLiteral = field(repr=False)
    ordinal: int
    reliable_supported: bool
    restricted_supported: bool
    reason: NumericReason | None


def _normal_form(text: str) -> tuple[str, tuple[int, ...]]:
    normalized = text.translate(_FULLWIDTH)
    offsets = tuple(range(len(text)))
    for pattern in (_SCIENTIFIC, _POWER, _UNSUPPORTED_FORM):
        pieces: list[str] = []
        positions: list[int] = []
        cursor = 0
        for match in pattern.finditer(normalized):
            pieces.append(normalized[cursor : match.start()])
            positions.extend(offsets[cursor : match.start()])
            if pattern is _UNSUPPORTED_FORM:
                # 即使未知形状后紧跟数字,也不能拼出合法的指数记法。
                replacement = "0..0"
            else:
                exponent = match["exponent"].lstrip("^").translate(_SUPERSCRIPT)
                mantissa = match.groupdict().get("mant") or "1"
                replacement = f"{mantissa}e{exponent}"
            pieces.append(replacement)
            positions.extend([offsets[match.start()]] * (len(replacement) - 1))
            positions.append(offsets[match.end() - 1])
            cursor = match.end()
        pieces.append(normalized[cursor:])
        positions.extend(offsets[cursor:])
        normalized = "".join(pieces)
        offsets = tuple(positions)
    return normalized, offsets


def _unit_at(text: str, start: int) -> tuple[str | None, int]:
    gap = re.match(r"\s*(?:-\s*)?", text[start:])
    assert gap is not None
    position = start + gap.end()
    for alias, canonical in UNIT_ALIASES:
        end = position + len(alias)
        if text.startswith(alias, position) and (
            end == len(text) or not _latin(text[end])
        ):
            return canonical, end
    return None, start


def _latin(character: str) -> bool:
    return "a" <= character <= "z" or "A" <= character <= "Z"


def _decimal(value: str) -> Decimal | None:
    parsed: Decimal | None = None
    if _VALID_NUMBER.fullmatch(value):
        try:
            parsed = Decimal(value.replace(",", ""))
        except InvalidOperation:
            return None
    return parsed


def _atoms(text: str) -> tuple[_Atom, ...]:
    result: list[_Atom] = []
    consumed = 0
    for match in _ATOM.finditer(text):
        if match.start() < consumed:
            continue
        raw = match[0].rstrip(".,")
        end = match.start() + len(raw)
        if not raw:
            continue
        unit, unit_end = _unit_at(text, end)
        if (
            match.start()
            and (
                _latin(text[match.start() - 1])
                or (
                    text[match.start() - 1] in "0123456789." and not raw.startswith("±")
                )
            )
        ) or (end < len(text) and _latin(text[end]) and unit is None):
            continue
        if _REFERENCE_PREFIX.search(text[: match.start()]):
            consumed = unit_end
            continue
        result.append(
            _Atom(
                _decimal(raw.removeprefix("±")),
                raw.startswith("±"),
                unit,
                match.start(),
                unit_end,
            )
        )
        consumed = unit_end
    return tuple(result)


def extract_numeric_literals(text: str) -> tuple[NumericLiteral, ...]:
    normalized, offsets = _normal_form(text)
    atoms = _atoms(normalized)
    literals: list[NumericLiteral] = []
    index = 0
    while index < len(atoms):
        first = atoms[index]
        last = first
        values: tuple[Decimal | None, ...] = (first.value,)
        uncertainty: tuple[bool, ...] = (first.uncertainty,)
        units: tuple[str | None, ...] = (first.unit,)
        if index + 1 < len(atoms):
            second = atoms[index + 1]
            between = normalized[first.end : second.start]
            joined_minus = (
                not between.strip()
                and normalized[second.start : second.start + 1] == "-"
            )
            if _RANGE.fullmatch(between) or joined_minus:
                last = second
                second_value = second.value
                if joined_minus and second_value is not None:
                    second_value = abs(second_value)
                values = (first.value, second_value)
                uncertainty = (first.uncertainty, second.uncertainty)
                units = (first.unit, second.unit)
                index += 1
        literal_text = text[offsets[first.start] : offsets[last.end - 1] + 1]
        literals.append(NumericLiteral(literal_text, values, uncertainty, units))
        index += 1
    return tuple(literals)


def _supports(
    literal: NumericLiteral, source: tuple[NumericLiteral, ...], with_unit: bool = True
) -> bool:
    if not literal.recognized:
        return False
    # 每个 source 参数只代表一条 provenance,不会跨切片凑范围端点。
    numbers = [
        (value, uncertain, unit if unit is not None else item.unit)
        for item in source
        if item.recognized
        for value, uncertain, unit in zip(
            item.values, item.uncertainty, item.units, strict=True
        )
    ]
    for index, (value, uncertain, declared_unit) in enumerate(
        zip(literal.values, literal.uncertainty, literal.units, strict=True)
    ):
        required_unit = declared_unit if declared_unit is not None else literal.unit
        if not any(
            value == source_value
            and uncertain == source_uncertain
            and (
                not with_unit
                or required_unit is None
                or required_unit == unit
                or (index < len(literal.values) - 1 and unit is None)
            )
            for source_value, source_uncertain, unit in numbers
        ):
            return False
    return True


def match_numbers(
    text: str, slices: tuple[SourceSlice, ...]
) -> tuple[NumericMatch, ...]:
    sources = [
        (extract_numeric_literals(item.text), item.kind != "text" or item.unreliable)
        for item in slices
    ]
    matches: list[NumericMatch] = []
    for ordinal, literal in enumerate(extract_numeric_literals(text)):
        reliable = any(
            _supports(literal, values)
            for values, restricted in sources
            if not restricted
        )
        restricted = any(
            _supports(literal, values) for values, restricted in sources if restricted
        )
        reason: NumericReason | None = None
        if not literal.recognized:
            reason = NumericReason.UNRECOGNIZED_NUMERIC_FORM
        elif not reliable and not restricted:
            if any(unit is not None for unit in literal.units) and any(
                _supports(literal, values, with_unit=False) for values, _ in sources
            ):
                reason = NumericReason.UNIT_NOT_SUPPORTED
            elif len(literal.values) == 2:
                reason = NumericReason.RANGE_NOT_SUPPORTED
            else:
                reason = NumericReason.NUMBER_NOT_SUPPORTED
        matches.append(NumericMatch(literal, ordinal, reliable, restricted, reason))
    return tuple(matches)
