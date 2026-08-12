"""
Consolidation module for merging multiple pycgt-format CSV files into one.

pycgt-format files written at different times carry different column sets (the
header is derived from config, which grows as cryptos are added), so they cannot
simply be concatenated. This module maps each input file's header onto the
canonical FIELDS header - the same mapping main.py applies at report time - and
writes a single datetime-sorted file.

Cell values are copied as raw strings: reformatting numbers here would perturb
cost basis downstream.
"""

import csv
from collections import Counter
from shared_def import FIELDS
from transaction import datetime_parser
from logger import logger

DATETIME_COLUMN = 'Datetime'


def _map_header(header, source_file):
  """
  Map a source header row onto canonical column positions.

  Returns a list with one entry per source column: the canonical column index,
  or None when the column has no FIELDS mapping.
  """
  canonical = list(FIELDS.keys())
  positions = []
  for name in header:
    positions.append(canonical.index(name) if name in FIELDS else None)

  unmapped = [name for name, pos in zip(header, positions) if pos is None]
  if unmapped:
    logger.info(f"{source_file}: columns without a FIELDS mapping: {unmapped}")

  return positions


def _read_file(path, canonical_width):
  """
  Read one pycgt-format CSV and return its rows in canonical column order.

  Warns about any unmapped column that actually carries data, and about rows
  with more values than the header declares - both mean data would be dropped.
  """
  rows = []
  dropped_columns = set()
  with open(path, 'r', newline='') as csvfile:
    csvcontent = csv.reader(csvfile, delimiter=',', quotechar='"')
    header = next(csvcontent, None)
    if header is None:
      logger.warning(f"{path}: file is empty, skipped")
      return rows

    positions = _map_header(header, path)
    for index, values in enumerate(csvcontent, start=2):
      if not any(value.strip() for value in values):
        continue

      row = [''] * canonical_width
      for name, position, value in zip(header, positions, values):
        if position is None:
          if value.strip():
            dropped_columns.add(name)
          continue
        row[position] = value
      rows.append(row)

      if len(values) > len(header):
        logger.warning(
            f"{path}:{index} has {len(values)} values but the header declares "
            f"{len(header)} columns - trailing values dropped: {values[len(header):]}")

  if dropped_columns:
    logger.warning(
        f"{path}: dropping non-empty columns with no FIELDS mapping: "
        f"{sorted(dropped_columns)}. Add them to config.toml to keep them.")

  logger.info(f"{path}: read {len(rows)} row(s)")
  return rows


def _warn_on_duplicates(rows):
  """
  Warn about rows that appear more than once across the merged inputs.

  Cumulative exchange exports (Bitstamp, IndependentReserve) overlap with
  previously transformed history, and a duplicated row silently double-counts a
  disposal.
  """
  counts = Counter(tuple(row) for row in rows)
  duplicates = {row: count for row, count in counts.items() if count > 1}
  if not duplicates:
    return

  total_extra = sum(count - 1 for count in duplicates.values())
  logger.warning(
      f"Found {len(duplicates)} distinct row(s) appearing more than once "
      f"({total_extra} extra row(s)). These are NOT removed - review whether "
      f"they are genuine repeats or an overlapping export.")
  for row, count in list(duplicates.items())[:10]:
    brief = [value for value in row[:6] if value]
    logger.warning(f"  x{count}: {brief}")


def consolidate(input_files, output_file):
  """
  Merge pycgt-format CSV files into one canonical-header file, datetime-sorted.

  All data rows are kept regardless of Operation value: rows main.py skips at
  report time (unrecognised operations) still belong in the archive.

  Args:
      input_files: List of pycgt-format CSV file paths
      output_file: Output CSV file path
  """
  canonical = list(FIELDS.keys())
  datetime_index = canonical.index(DATETIME_COLUMN)

  rows = []
  for path in input_files:
    rows.extend(_read_file(path, len(canonical)))

  if not rows:
    raise ValueError('No data rows found in the input files')

  _warn_on_duplicates(rows)

  # Sort by datetime ascending, matching main.py's ordering so that the merged
  # file produces an identical report. Python's sort is stable, so rows sharing
  # a datetime keep their original file-then-row order.
  datable = []
  undatable = []
  for row in rows:
    raw = row[datetime_index]
    try:
      parsed = datetime_parser(raw)
    except BaseException as _:
      parsed = None
    if parsed is None:
      undatable.append(row)
    else:
      datable.append((parsed, row))

  datable.sort(key=lambda item: item[0])
  sorted_rows = [item[1] for item in datable] + undatable

  if undatable:
    logger.warning(
        f"{len(undatable)} row(s) have a missing or unparseable {DATETIME_COLUMN} "
        f"and were placed at the end of {output_file}")

  with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter=',', quotechar='"')
    writer.writerow(canonical)
    writer.writerows(sorted_rows)

  logger.info(
      f"Consolidated {len(rows)} row(s) from {len(input_files)} file(s) into "
      f"{output_file} ({len(canonical)} columns)")
