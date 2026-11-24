# Original insurance workbook intake

[BH-18](https://maiteai.atlassian.net/browse/BH-18) tracks local intake for P1 Data & RAG. The Wave 3 application continues to use the [synthetic staging inputs](STAGING_PILOT.md). The legacy API reads prepared CSVs. This stage reads the original insurer workbooks directly in read-only mode. It produces an aggregate validation report with SHA-256 provenance, per-sheet row and cached-error counts, and relationship checks. The consolidated SQLite export is independent of this stage.

## Reproduce locally

Use Python 3.12 in an activated virtual environment from the repository root.

1. Install the pinned tools with `python -m pip install -r scripts/source-dvc-requirements.txt`.
2. Copy one authorized set of original workbooks into `source_inputs/workbooks/` using the names below. The original and v2 archive copies of these three files matched byte for byte.

   | Original filename | Local filename |
   | --- | --- |
   | `Données_Assurance_S1.2_S2.2.xlsx` | `insurance.xlsx` |
   | `Description_garanties.xlsx` | `guarantee-descriptions.xlsx` |
   | `Mapping produits vs profils_cibles.xlsx` | `target-profiles.xlsx` |

3. Run `dvc status source_inputs/workbooks.dvc` to check the snapshot. If the files match the pointer and only the cache is missing, run `dvc commit source_inputs/workbooks.dvc` to populate it. If the inputs differ, obtain the recorded source version or review the new snapshot explicitly before running `dvc add source_inputs/workbooks`.
4. Run `dvc repro`, then `dvc status`. Read the local report at `data/source-quality.json`. Unmatched keys and repeated coverage groups are reported without altering the workbooks.

Git tracks the stage, lockfile, and dataset pointer. The workbooks, report, and DVC cache are Git-ignored. For another authorized checkout, configure an approved private store with `dvc remote add --local -d private PATH` and use `dvc pull`. No shared store is configured in Git. Only a reviewed and authorized projection can enter the pilot or a cloud environment.
