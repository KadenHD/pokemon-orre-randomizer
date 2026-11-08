"""A shared, versioned Unown form draw for Colosseum and XD."""

from hashlib import sha256


_FORM_SUFFIXES = (*"abcdefghijklmnopqrstuvwxyz", "ex", "qu")


def unown_form(seed: str) -> int:
    digest = sha256(b"orre-unown-form-v1\0" + seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % len(_FORM_SUFFIXES)


def unown_suffix(form: int) -> str:
    if not 0 <= form < len(_FORM_SUFFIXES):
        raise ValueError("Unown form must be between 0 and 27")
    return _FORM_SUFFIXES[form]
