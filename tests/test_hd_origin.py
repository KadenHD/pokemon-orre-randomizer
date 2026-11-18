"""The deployment probe must distinguish range support from full integrity."""
from dataclasses import replace
import hashlib
import io
import unittest
from unittest.mock import patch

from orre_randomizer.hd_packs import Pack, Part
from scripts.verify_hd_origin import verify_origin, verify_github_manifest


class Response(io.BytesIO):
    def __init__(self, data=b"", *, status=200, headers=None, url="https://hd.example/archive.zip"):
        super().__init__(data)
        self.status, self.headers, self.url = status, headers or {}, url

    def geturl(self):
        return self.url


class OriginVerification(unittest.TestCase):
    def setUp(self):
        self.payload = b"PK\x03\x04" + bytes(range(128))
        digest = hashlib.sha256(self.payload).hexdigest()
        self.packs = {game: Pack(game, "test", len(self.payload),
            (Part("", digest, len(self.payload)),)) for game in ("colosseum", "xd")}
        self.catalog = patch("scripts.verify_hd_origin.PACKS", self.packs)
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def respond(self, request, **kwargs):
        size = len(self.payload)
        if request.method == "HEAD":
            return Response(headers={"Content-Length": str(size)})
        interval = request.get_header("Range")
        if interval:
            first, last = map(int, interval.removeprefix("bytes=").split("-"))
            return Response(self.payload[first:last + 1], status=206,
                headers={"Content-Range": f"bytes {first}-{last}/{size}"})
        return Response(self.payload)

    def test_ranges_do_not_claim_full_integrity(self):
        with patch("urllib.request.urlopen", side_effect=self.respond) as requests:
            result = verify_origin("https://hd.example")
        self.assertEqual(requests.call_count, 6)
        self.assertFalse(result["full_integrity_verified"])
        self.assertTrue(all(row["verified_sha256"] is None for row in result["archives"]))
        self.assertFalse(result["local_archives_written"])
        self.assertFalse(result["production_config_changed"])

    def test_complete_hash_covers_both_archives(self):
        with patch("urllib.request.urlopen", side_effect=self.respond):
            result = verify_origin("https://hd.example", full_sha256=True)
        self.assertTrue(result["full_integrity_verified"])
        for row in result["archives"]:
            self.assertEqual(row["verified_sha256"], hashlib.sha256(self.payload).hexdigest())

    def test_wrong_range_or_size_is_refused(self):
        original = self.respond
        for error in ("range", "size"):
            def broken(request, **kwargs):
                response = original(request, **kwargs)
                if error == "range" and request.get_header("Range"):
                    response.headers["Content-Range"] = "bytes 1-64/132"
                if error == "size" and request.method == "HEAD":
                    response.headers["Content-Length"] = "1"
                return response
            with self.subTest(error=error), patch("urllib.request.urlopen", side_effect=broken):
                with self.assertRaises(ValueError):
                    verify_origin("https://hd.example")

    def test_corrupt_complete_archive_is_refused(self):
        self.packs["xd"] = replace(self.packs["xd"], parts=(
            replace(self.packs["xd"].parts[0], sha256="0" * 64),))
        with patch("urllib.request.urlopen", side_effect=self.respond):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_origin("https://hd.example", full_sha256=True)

    def test_credentials_and_http_are_refused_before_network(self):
        for source in ("http://hd.example", "https://user:secret@hd.example", "https://hd.example?key=secret"):
            with self.subTest(source=source), patch("urllib.request.urlopen") as request:
                with self.assertRaises(ValueError):
                    verify_origin(source)
                request.assert_not_called()

    def test_redirect_to_http_is_refused(self):
        with patch("urllib.request.urlopen", return_value=Response(url="http://hd.example/archive.zip")):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                verify_origin("https://hd.example")

    def github_fixture(self):
        assets, archives, files = [], [], {}
        for game in ("colosseum", "xd"):
            names = []
            chunks = [self.payload] if game == "colosseum" else [self.payload[:60], self.payload[60:]]
            offset = 0
            for index, chunk in enumerate(chunks):
                name = f"{game}.zip.{index + 1:03d}"
                files[name] = chunk
                names.append(name)
                assets.append({"name": name, "game": game, "offset": offset,
                    "size": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
                offset += len(chunk)
            archives.append({"game": game, "version": "test", "size": len(self.payload),
                "sha256": hashlib.sha256(self.payload).hexdigest(), "assets": names})
        return {"proposed_repository": "owner/hd-packs", "proposed_tag": "packs-test",
                "assets": assets, "archives": archives}, files

    def github_responses(self, files):
        def respond(request, **kwargs):
            data = files[request.full_url.rsplit("/", 1)[-1]]
            if request.method == "HEAD":
                return Response(headers={"Content-Length": str(len(data))})
            interval = request.get_header("Range")
            if interval:
                first, last = map(int, interval.removeprefix("bytes=").split("-"))
                return Response(data[first:last + 1], status=206,
                    headers={"Content-Range": f"bytes {first}-{last}/{len(data)}"})
            return Response(data)
        return respond

    def test_github_fragments_verify_original_archive_not_only_individual_parts(self):
        manifest, files = self.github_fixture()
        with patch("urllib.request.urlopen", side_effect=self.github_responses(files)):
            result = verify_github_manifest(manifest, full_sha256=True)
        self.assertTrue(result["full_integrity_verified"])
        self.assertEqual(len(result["archives"][1]["assets"]), 2)
        self.assertEqual(result["archives"][1]["verified_archive_sha256"],
                         hashlib.sha256(self.payload).hexdigest())

    def test_github_probe_does_not_claim_complete_archive_integrity(self):
        manifest, files = self.github_fixture()
        with patch("urllib.request.urlopen", side_effect=self.github_responses(files)):
            result = verify_github_manifest(manifest)
        self.assertFalse(result["full_integrity_verified"])
        self.assertIsNone(result["archives"][1]["verified_archive_sha256"])

    def test_published_manifest_uses_repository_and_tag_without_staging_fields(self):
        manifest, files = self.github_fixture()
        manifest["repository"] = manifest.pop("proposed_repository")
        manifest["tag"] = manifest.pop("proposed_tag")
        with patch("urllib.request.urlopen", side_effect=self.github_responses(files)):
            result = verify_github_manifest(manifest, full_sha256=True)
        self.assertTrue(result["full_integrity_verified"])
        self.assertEqual(result["repository"], "owner/hd-packs")

    def test_github_manifest_cannot_replace_the_pinned_original_with_other_valid_fragments(self):
        manifest, files = self.github_fixture()
        name = manifest["archives"][1]["assets"][1]
        files[name] = b"X" + files[name][1:]
        next(asset for asset in manifest["assets"] if asset["name"] == name)["sha256"] = hashlib.sha256(files[name]).hexdigest()
        with patch("urllib.request.urlopen", side_effect=self.github_responses(files)):
            with self.assertRaisesRegex(ValueError, "Reassembled original"):
                verify_github_manifest(manifest, full_sha256=True)


if __name__ == "__main__":
    unittest.main()
