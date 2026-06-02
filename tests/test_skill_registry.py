from skills import SKILLS, load_catalog


def test_registry_has_six_skills():
    expected = {"stats-skill", "viz-skill", "trend-skill",
                "correlation-skill", "distribution-skill", "profile-skill"}
    assert expected.issubset(set(SKILLS.keys()))


def test_every_spec_executable_and_has_skillmd():
    for spec in SKILLS.values():
        assert callable(spec.execute)
        assert spec.path.exists()


def test_catalog_concatenates_skillmd():
    catalog = load_catalog()
    assert "stats-skill" in catalog and "viz-skill" in catalog
    assert "Return JSON only" in catalog
