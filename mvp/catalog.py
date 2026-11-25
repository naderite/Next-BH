"""Build and open the P1 housing evidence artifact in Chroma."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import chromadb
from chromadb.config import Settings

SOURCE = Path(__file__).with_name("catalog.json")
DEFAULT_INDEX = Path("data/housing-evidence")
MANIFEST = "manifest.json"


def source():
    content = SOURCE.read_bytes()
    catalog = json.loads(content)
    digest = sha256(content).hexdigest()
    return catalog["entries"], {
        "catalog_version": catalog["version"],
        "source_sha256": digest,
        "collection": f"housing-{digest[:24]}",
    }


def storage(path):
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def build_index(path):
    entries, manifest = source()
    collection = storage(path).get_or_create_collection(manifest["collection"], embedding_function=None)
    slots = sorted(entries)
    for index, slot in enumerate(slots):
        entry = entries[slot]
        collection.upsert(
            ids=[entry["id"]],
            documents=[entry["excerpt"]],
            metadatas=[{"slot": slot, "document": entry["document"], "locator": entry["locator"]}],
            embeddings=[[float(index == position) for position in range(len(slots))]],
        )
    temporary = path / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path / MANIFEST)
    return manifest


class EvidenceIndex:
    def __init__(self, path):
        entries, expected = source()
        if not (path / MANIFEST).is_file():
            raise ValueError("Build the housing evidence index with python -m mvp.catalog.")
        manifest = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
        if manifest != expected:
            raise ValueError("The evidence manifest does not match the bundled catalog. Rebuild the index.")
        self.version = manifest["catalog_version"]
        self.digest = manifest["source_sha256"]
        collection = storage(path).get_collection(manifest["collection"], embedding_function=None)
        result = collection.get(include=["documents", "metadatas"])
        actual = {}
        for evidence_id, excerpt, meta in zip(
            result["ids"], result["documents"], result["metadatas"], strict=True
        ):
            slot = meta["slot"]
            if slot in actual:
                raise ValueError("The housing evidence index contains a duplicate product slot.")
            actual[slot] = {
                "id": evidence_id,
                "excerpt": excerpt,
                "document": meta["document"],
                "locator": meta["locator"],
            }
        if actual != entries:
            raise ValueError("The housing evidence index differs from its source. Rebuild in a fresh directory.")
        self.entries = actual


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    print(json.dumps(build_index(args.output), indent=2))
