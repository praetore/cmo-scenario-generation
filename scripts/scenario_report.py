"""Shared helpers for scenario preflight validation output."""


def empty_report():
    return {"errors": [], "warnings": [], "ok": []}


def extend_report(target, source):
    """Merge errors/warnings/ok lists from a sub-check into target."""
    if not source:
        return
    target["errors"].extend(source.get("errors") or [])
    target["warnings"].extend(source.get("warnings") or [])
    target["ok"].extend(source.get("ok") or [])


def run_check(report, fn, *args, **kwargs):
    """Run one validator; merge its report into report."""
    extend_report(report, fn(*args, **kwargs))
