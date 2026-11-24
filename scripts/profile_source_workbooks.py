"""Profile restricted source workbooks without writing record-level data."""

from collections import Counter
from contextlib import closing
from hashlib import file_digest
import json
from pathlib import Path

from openpyxl import load_workbook


WORKBOOKS = {
    "insurance.xlsx": {
        "personne_physique": ("REF_PERSONNE",),
        "personne_morale": ("REF_PERSONNE",),
        "Contrats": ("NUM_CONTRAT", "REF_PERSONNE"),
        "Garantie_contrat": ("NUM_CONTRAT", "CODE_GARANTIE"),
        "sinistres": ("NUM_SINISTRE", "NUM_CONTRAT"),
        "Mapping_Produits": (),
    },
    "guarantee-descriptions.xlsx": {"Sheet1": ()},
    "target-profiles.xlsx": {"Sheet1": ()},
}
SOURCE_DIR = Path("source_inputs/workbooks")
REPORT_PATH = Path("data/source-quality.json")


def profile_workbook(path, schema):
    with path.open("rb") as source:
        sha256 = file_digest(source, "sha256").hexdigest()

    sheets = {}
    keys = {}
    with closing(load_workbook(path, read_only=True, data_only=True)) as workbook:
        if set(workbook.sheetnames) != schema.keys():
            raise ValueError(f"Unexpected sheet inventory in {path.name}")

        for sheet_name, columns in schema.items():
            sheet = workbook[sheet_name]
            sheet.reset_dimensions()
            rows = iter(sheet.iter_rows())
            header = [cell.value for cell in next(rows, ())]
            if not any(value is not None for value in header):
                raise ValueError(f"Missing header in {path.name}/{sheet_name}")
            if any(header.count(column) != 1 for column in columns):
                raise ValueError(f"Missing or ambiguous key columns in {path.name}/{sheet_name}")

            positions = [header.index(column) for column in columns]
            row_count = 0
            errors = 0
            counts = Counter()
            for row in rows:
                if all(cell.value is None for cell in row):
                    continue
                row_count += 1
                errors += sum(cell.data_type == "e" for cell in row)
                if positions:
                    key = tuple(
                        row[index].value
                        if index < len(row) and row[index].data_type != "e" else None
                        for index in positions
                    )
                    counts[key] += 1

            sheets[sheet_name] = {"rows": row_count, "cached_excel_errors": errors}
            keys[sheet_name] = counts

    return {"sha256": sha256, "sheets": sheets}, keys


def profile_relationships(keys):
    customer_keys = keys["personne_physique"].keys() | keys["personne_morale"].keys()
    people = {key for (key,) in customer_keys if key is not None}
    contracts = {key for key, _ in keys["Contrats"] if key is not None}
    covered_contracts = {key for key, _ in keys["Garantie_contrat"] if key is not None}
    return {
        "contracts_without_customer": sum(
            count for (_, customer), count in keys["Contrats"].items() if customer not in people
        ),
        "guarantee_lines_without_contract": sum(
            count for (contract, _), count in keys["Garantie_contrat"].items()
            if contract not in contracts
        ),
        "claims_without_contract": sum(
            count for (_, contract), count in keys["sinistres"].items() if contract not in contracts
        ),
        "contracts_without_guarantee": len(contracts - covered_contracts),
        "repeated_contract_guarantee_groups": sum(
            count > 1 for count in keys["Garantie_contrat"].values()
        ),
    }


def main():
    reports = {}
    for filename, schema in WORKBOOKS.items():
        report, keys = profile_workbook(SOURCE_DIR / filename, schema)
        reports[filename] = report
        if filename == "insurance.xlsx":
            relationships = profile_relationships(keys)

    output = {"workbooks": reports, "relationships": relationships}
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
