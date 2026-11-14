import importlib


def test_pipeline_subpackages_exist() -> None:
    for name in ("fetch", "ingest", "coreg", "derived", "package", "ground_images"):
        importlib.import_module(f"marswalk_pipeline.{name}")
