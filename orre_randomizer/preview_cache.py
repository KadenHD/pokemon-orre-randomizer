"""One owned, temporary RVZ decompression per application window.

No cache survives the owner closing it. Source and decoded bytes are hashed on
every use; the cache never treats timestamps as proof of ROM identity. A lease
owns the only active reader, so invalidation cannot delete an ISO in use.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import threading


@dataclass(frozen=True)
class PreviewInput:
    iso: Path
    iso_hash: str
    cache_hit: bool


class PreviewCache:
    def __init__(self):
        self._gate = threading.Lock()
        self._state = threading.Lock()
        self._closed = False
        self._active = False
        self._invalidate = False
        self._temporary = None
        self._key = None
        self._iso_hash = None

    def _discard(self):
        temporary = self._temporary
        self._temporary = self._key = self._iso_hash = None
        if temporary is not None:
            temporary.cleanup()

    def invalidate(self):
        """Release an idle conversion, or defer deletion until its reader exits."""
        with self._state:
            self._invalidate = True
            if not self._active:
                self._discard()

    def close(self):
        """Prevent new users; an in-flight preview retains its files until exit."""
        with self._state:
            self._closed = True
            self._invalidate = True
            if not self._active:
                self._discard()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def lease(self, source: Path, source_hash: str, dolphin_tool: Path,
              progress, cancel: threading.Event):
        from . import service

        while not self._gate.acquire(timeout=0.05):
            service.checkpoint(cancel)
            with self._state:
                if self._closed:
                    raise service.Cancelled("Aperçu annulé.")
        failed = True
        entered = False
        try:
            service.checkpoint(cancel)
            with self._state:
                if self._closed:
                    raise service.Cancelled("Aperçu annulé.")
                self._active = entered = True
                invalidated = self._invalidate
                self._invalidate = False
            tool = Path(dolphin_tool).resolve()
            key = (str(source.resolve()), source_hash, str(tool), service.file_hash(tool, cancel))
            if invalidated or key != self._key:
                self._discard()
            hit = self._temporary is not None
            if hit:
                iso = Path(self._temporary.name) / "source.iso"
                if not iso.is_file() or service.file_hash(iso, cancel) != self._iso_hash:
                    # Reject unexpected changes rather than quietly serving a
                    # stale/corrupt decoded ROM or changing the recorded identity.
                    raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
            else:
                self._temporary = tempfile.TemporaryDirectory(prefix="orre-preview-")
                work = Path(self._temporary.name)
                needed = service.ISO_SIZE + 64 * 1024**2
                if shutil.disk_usage(work).free < needed:
                    raise service.UserError("Espace disque insuffisant : il faut au moins {needed:.1f} Gio libres dans le dossier de sortie.",
                                            needed=needed / 1024**3)
                progress(8, "Conversion RVZ → ISO avec DolphinTool…")
                iso = work / "source.iso"
                service.convert(tool, source, iso, work, cancel)
                self._iso_hash = service.file_hash(iso, cancel)
                self._key = key
            service.checkpoint(cancel)
            yield PreviewInput(iso, self._iso_hash, hit)
            service.checkpoint(cancel)
            if service.file_hash(iso, cancel) != self._iso_hash:
                raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
            failed = False
        finally:
            with self._state:
                if entered:
                    self._active = False
                if failed or self._closed or self._invalidate:
                    self._discard()
                    self._invalidate = False
            self._gate.release()
