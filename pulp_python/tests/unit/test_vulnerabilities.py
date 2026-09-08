from pulp_python.app.osv import osv_to_pypi_vulnerabilities


def test_osv_to_pypi_maps_fixed_versions_and_skips_git_shas():
    vulns = [
        {
            "id": "PYSEC-2020-35",
            "aliases": ["CVE-2020-7471"],
            "details": "SQL injection",
            "summary": None,
            "withdrawn": None,
            "affected": [
                {
                    "package": {"name": "django", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [
                                {"introduced": "3.0"},
                                {"fixed": "3.0.3"},
                                {"fixed": "eb31d845323618d688ad429479c6dda973056136"},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    result = osv_to_pypi_vulnerabilities(vulns)

    assert result == [
        {
            "id": "PYSEC-2020-35",
            "source": "osv",
            "link": "https://osv.dev/vulnerability/PYSEC-2020-35",
            "aliases": ["CVE-2020-7471"],
            "details": "SQL injection",
            "summary": None,
            "fixed_in": ["3.0.3"],
            "withdrawn": None,
        }
    ]


def test_osv_to_pypi_deduplicates_by_id():
    vulns = [
        {"id": "GHSA-aaaa", "aliases": ["CVE-1"], "details": "first"},
        {"id": "GHSA-aaaa", "aliases": ["CVE-1"], "details": "duplicate"},
        {"id": "GHSA-bbbb", "aliases": [], "details": "other"},
    ]

    result = osv_to_pypi_vulnerabilities(vulns)

    assert [v["id"] for v in result] == ["GHSA-aaaa", "GHSA-bbbb"]
    assert result[0]["details"] == "first"


def test_osv_to_pypi_preserves_withdrawn_and_missing_summary():
    vulns = [
        {
            "id": "PYSEC-2022-XXX",
            "aliases": ["CVE-2022-XXXXX"],
            "details": "A long description.",
            "withdrawn": "2022-06-28T16:39:06Z",
            "affected": [
                {
                    "ranges": [{"events": [{"fixed": "1.2.3"}]}],
                }
            ],
        }
    ]

    result = osv_to_pypi_vulnerabilities(vulns)

    assert result[0]["summary"] is None
    assert result[0]["withdrawn"] == "2022-06-28T16:39:06Z"
    assert result[0]["fixed_in"] == ["1.2.3"]


def test_osv_to_pypi_empty_and_missing_ids():
    assert osv_to_pypi_vulnerabilities(None) == []
    assert osv_to_pypi_vulnerabilities([]) == []
    assert osv_to_pypi_vulnerabilities([{"details": "no id"}]) == []
