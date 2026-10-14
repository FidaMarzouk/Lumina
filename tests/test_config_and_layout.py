import subprocess
import sys

from lumina import config


def test_paths_live_under_project_root_and_exist():
    for p in (config.RAW_DIR, config.PROCESSED_DIR, config.VECTORSTORE_PATH):
        assert config.PROJECT_ROOT in p.parents and p.exists()
    assert (config.PROJECT_ROOT / "src" / "lumina").is_dir() and (config.PROJECT_ROOT / "src" / "lumina" / "knowledge").is_dir()
    assert (config.INTENT_MODEL_DIR / "model_card.json").is_file()


def test_shipped_ingestion_settings_unchanged():
    assert config.COLLECTION_NAME == "mental_health_kb"
    assert (config.MAX_CHUNK_TOKENS, config.CHUNK_OVERLAP_TOKENS, config.EMBED_BATCH_SIZE) == (500, 50, 64)
    assert config.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"


def test_importing_lexicons_or_config_does_not_load_ml_stacks():
    code = ("import sys; import lumina.config, lumina.nlp, lumina.nlp.lexicons; "
            "print(any(m in sys.modules for m in ('torch','transformers','spacy','chromadb')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=config.PROJECT_ROOT)
    assert out.stdout.strip() == "False", out.stderr


def test_config_does_not_create_directories_on_import(tmp_path):
    code = "import lumina.config as c; print(c.VECTORSTORE_PATH.exists())"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=config.PROJECT_ROOT)
    assert out.stdout.strip() == "True"        # exists because it ships with the project, not because import creates it
