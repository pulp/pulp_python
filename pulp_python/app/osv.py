from packaging.version import InvalidVersion, Version


def _osv_fixed_in(vuln):
    """Extract PEP 440 fixed versions from an OSV vulnerability record."""
    fixed = []
    seen = set()
    for affected in vuln.get("affected") or []:
        for range_ in affected.get("ranges") or []:
            for event in range_.get("events") or []:
                if "fixed" not in event:
                    continue
                version = event["fixed"]
                if version in seen:
                    continue
                try:
                    Version(version)
                except InvalidVersion:
                    continue
                seen.add(version)
                fixed.append(version)
    return fixed


def osv_to_pypi_vulnerabilities(vulns):
    """Trim OSV vulnerability records to the Warehouse JSON API shape."""
    seen = {}
    for vuln in vulns or []:
        vuln_id = vuln.get("id")
        if not vuln_id or vuln_id in seen:
            continue
        seen[vuln_id] = {
            "id": vuln_id,
            "source": "osv",
            "link": f"https://osv.dev/vulnerability/{vuln_id}",
            "aliases": vuln.get("aliases") or [],
            "details": vuln.get("details"),
            "summary": vuln.get("summary"),
            "fixed_in": _osv_fixed_in(vuln),
            "withdrawn": vuln.get("withdrawn"),
        }
    return list(seen.values())
