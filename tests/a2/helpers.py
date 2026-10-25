from pathlib import Path


def package(path: Path, readme="", name="fixture"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "DESCRIPTION").write_text(f"Package: {name}\nVersion: 0.0.1\nTitle: Fixture\nDescription: Test fixture.\nLicense: MIT\nAuthors@R: person('A', 'B', email='a@example.org', role=c('aut','cre'))\n")
    (path / "NAMESPACE").write_text("")
    (path / "README.md").write_text(readme)
    return path
