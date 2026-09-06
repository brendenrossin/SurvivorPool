"""The models and the migration SQL must describe the same schema.

Tests build the schema from SQLAlchemy metadata on SQLite; production builds it
from `db/migrations.sql` on Postgres. Nothing compared the two, so a column or
an index added to one and not the other shipped green - which is how
`api/models.py` came to declare one index against the SQL's five.

The comparison works by compiling each model index back to Postgres DDL and
running it through the same parser as the .sql file, so both sides are read the
same way and neither gets a more forgiving reading than the other.

Deliberately strict about what it can parse: an unrecognised statement raises
rather than being skipped, because a silently ignored `ALTER TABLE` is exactly
the drift this is here to catch.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from api.models import Base

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations.sql"

# Leading words that mean a CREATE TABLE body line is a table constraint rather
# than a column definition.
_CONSTRAINT_KEYWORDS = {
    "unique", "primary", "foreign", "check", "constraint", "exclude", "like",
}

_CREATE_TABLE = re.compile(
    r"^create\s+table\s+(?:if\s+not\s+exists\s+)?(\w+)\s*\((.*)\)$",
    re.IGNORECASE | re.DOTALL,
)
_CREATE_INDEX = re.compile(
    r"^create\s+(unique\s+)?index\s+(?:if\s+not\s+exists\s+)?(\w+)\s+"
    r"on\s+(\w+)\s*\((.*?)\)\s*(?:where\s+(.*))?$",
    re.IGNORECASE | re.DOTALL,
)
_DROP_INDEX = re.compile(
    r"^drop\s+index\s+(?:if\s+exists\s+)?(\w+)$", re.IGNORECASE
)


class ParsedIndex(dict):
    """An index reduced to the facts both sides can be held to."""


def _strip_comments(sql: str) -> str:
    """Remove `--` comments, leaving anything inside single quotes alone."""
    out = []
    for line in sql.splitlines():
        in_quote = False
        cut = len(line)
        i = 0
        while i < len(line):
            char = line[i]
            if char == "'":
                in_quote = not in_quote
            elif char == "-" and not in_quote and line[i:i + 2] == "--":
                cut = i
                break
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


def _split_top_level(body: str) -> list[str]:
    """Split on commas that are not inside parentheses."""
    parts, depth, current = [], 0, []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _normalise(text: str | None) -> str | None:
    return " ".join(text.lower().split()) if text else None


def _parse_index_columns(columns: str) -> tuple[tuple[str, str], ...]:
    """(name, direction) per indexed column; direction defaults to ASC."""
    parsed = []
    for part in _split_top_level(columns):
        tokens = part.split()
        name = tokens[0].strip('"')
        direction = "DESC" if len(tokens) > 1 and tokens[1].upper() == "DESC" else "ASC"
        parsed.append((name, direction))
    return tuple(parsed)


def _parse_create_index(statement: str) -> ParsedIndex:
    match = _CREATE_INDEX.match(statement)
    if not match:
        raise ValueError(f"Cannot parse CREATE INDEX: {statement!r}")
    unique, name, table, columns, where = match.groups()
    return ParsedIndex(
        name=name.lower(),
        table=table.lower(),
        columns=_parse_index_columns(columns),
        unique=bool(unique),
        where=_normalise(where),
    )


def parse_migrations_sql(sql: str) -> tuple[dict, dict]:
    """(tables -> column names, index name -> ParsedIndex) from the .sql file.

    Raises on any statement it does not recognise rather than skipping it.
    """
    tables: dict[str, set[str]] = {}
    indexes: dict[str, ParsedIndex] = {}

    for raw in _strip_comments(sql).split(";"):
        statement = " ".join(raw.split())
        if not statement:
            continue

        table_match = _CREATE_TABLE.match(statement)
        if table_match:
            name, body = table_match.groups()
            columns = set()
            for part in _split_top_level(body):
                # Split on "(" too: a table constraint may be written
                # UNIQUE(a, b) with no space before the paren.
                first = re.split(r"[\s(]", part, maxsplit=1)[0].lower().strip('"')
                if first not in _CONSTRAINT_KEYWORDS:
                    columns.add(first)
            tables[name.lower()] = columns
            continue

        if _CREATE_INDEX.match(statement):
            index = _parse_create_index(statement)
            indexes[index["name"]] = index
            continue

        drop_match = _DROP_INDEX.match(statement)
        if drop_match:
            # A dropped index is not part of the schema even if an earlier
            # statement created it.
            indexes.pop(drop_match.group(1).lower(), None)
            continue

        raise ValueError(
            f"Unrecognised statement in db/migrations.sql - the parity parser "
            f"must be taught this before the file can be trusted: {statement!r}"
        )

    return tables, indexes


def model_schema() -> tuple[dict, dict]:
    """The same two structures, read off SQLAlchemy metadata."""
    tables = {
        name.lower(): {column.name.lower() for column in table.columns}
        for name, table in Base.metadata.tables.items()
    }

    indexes = {}
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
            parsed = _parse_create_index(" ".join(ddl.split()))
            indexes[parsed["name"]] = parsed
    return tables, indexes


@pytest.fixture(scope="module")
def sql_schema():
    return parse_migrations_sql(MIGRATIONS.read_text())


@pytest.fixture(scope="module")
def orm_schema():
    return model_schema()


# --- the parser itself ------------------------------------------------------

def test_the_parser_rejects_what_it_does_not_understand():
    """A statement it silently skipped would be drift it cannot see."""
    with pytest.raises(ValueError, match="Unrecognised statement"):
        parse_migrations_sql("ALTER TABLE games ADD COLUMN surprise INT;")


def test_the_parser_reads_a_partial_unique_index():
    _, indexes = parse_migrations_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix ON t (a, b DESC) WHERE a IS NOT NULL;"
    )
    assert indexes["ix"]["unique"] is True
    assert indexes["ix"]["columns"] == (("a", "ASC"), ("b", "DESC"))
    assert indexes["ix"]["where"] == "a is not null"


def test_the_parser_honours_a_later_drop():
    _, indexes = parse_migrations_sql(
        "CREATE INDEX ix ON t (a); DROP INDEX IF EXISTS ix;"
    )
    assert indexes == {}


def test_the_parser_ignores_commented_out_sql():
    tables, _ = parse_migrations_sql(
        "-- CREATE TABLE ghost (a INT);\nCREATE TABLE real_t (a INT);"
    )
    assert set(tables) == {"real_t"}


# --- the actual parity check ------------------------------------------------

def test_the_same_tables_are_declared_on_both_sides(sql_schema, orm_schema):
    assert set(sql_schema[0]) == set(orm_schema[0])


def test_every_shared_table_has_the_same_columns(sql_schema, orm_schema):
    sql_tables, orm_tables = sql_schema[0], orm_schema[0]
    drift = {
        name: {
            "only_in_sql": sorted(sql_tables[name] - orm_tables[name]),
            "only_in_models": sorted(orm_tables[name] - sql_tables[name]),
        }
        for name in sorted(set(sql_tables) & set(orm_tables))
        if sql_tables[name] != orm_tables[name]
    }
    assert drift == {}, f"column drift between api/models.py and db/migrations.sql: {drift}"


def test_the_same_indexes_are_declared_on_both_sides(sql_schema, orm_schema):
    sql_indexes, orm_indexes = sql_schema[1], orm_schema[1]
    assert sorted(sql_indexes) == sorted(orm_indexes), (
        f"only in db/migrations.sql: {sorted(set(sql_indexes) - set(orm_indexes))}; "
        f"only in api/models.py: {sorted(set(orm_indexes) - set(sql_indexes))}"
    )


def test_every_shared_index_covers_the_same_columns_in_the_same_order(
        sql_schema, orm_schema):
    sql_indexes, orm_indexes = sql_schema[1], orm_schema[1]
    drift = {
        name: {"sql": sql_indexes[name], "models": orm_indexes[name]}
        for name in sorted(set(sql_indexes) & set(orm_indexes))
        if sql_indexes[name] != orm_indexes[name]
    }
    assert drift == {}, f"index definitions differ: {drift}"
