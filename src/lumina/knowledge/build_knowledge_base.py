"""
lumina/knowledge/build_knowledge_base.py   (new)

One command for the whole RAG ingestion:

    python -m lumina.knowledge.build_knowledge_base            # clean -> embed
    python -m lumina.knowledge.build_knowledge_base --stages clean
    python -m lumina.knowledge.build_knowledge_base --stages embed

    data/knowledge/raw/*.jsonl --clean--> data/knowledge/processed/ --embed--> data/index/<version>/ (+ manifest.json)

The raw files come from the original Phase 2 scrapers, which are not in the repository; the raw data is
frozen in data/snapshots/v0 and cleaned/re-chunked here (see cleaning.py for the v1 fixes).
"""
import argparse


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stages", nargs="+", choices=["clean", "embed"], default=["clean", "embed"])
    args = ap.parse_args(argv)

    if "clean" in args.stages:
        from . import cleaning
        cleaning.run_pipeline()
    if "embed" in args.stages:
        from . import embed_and_store
        embed_and_store.build_vector_store()


if __name__ == "__main__":
    main()
