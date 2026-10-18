#!/usr/bin/env python3
"""Dependency-free checks. Inspect only allowlisted public files; never print secrets."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"
REVIEW_FILE = REPO / "docs/release/website-publication.json"
BASE = "https://tuhuzbayeu.github.io/keep-or-skip-site/"
ALLOWED = {"index.html", "privacy/index.html", "support/index.html", "styles.css",
           "assets/stack-review.jpg", ".nojekyll", "robots.txt", "sitemap.xml"}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.meta, self.errors = [], set(), [], {}, []
        self.tags = []

    def handle_decl(self, decl):
        if decl.lower() != "doctype html": self.errors.append("Unexpected declaration")

    def handle_starttag(self, tag, pairs):
        a = dict(pairs)
        self.tags.append(tag)
        if tag in {"script", "iframe", "form", "object", "embed", "base"}:
            self.errors.append("Active or embedded content is prohibited")
        if any(k.startswith("on") or k == "style" for k in a):
            self.errors.append("Inline scripts/styles are prohibited")
        if tag == "html" and a.get("lang") != "en": self.errors.append("Missing English language")
        if "id" in a:
            if a["id"] in self.ids: self.errors.append("Duplicate ID")
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if key in a: self.links.append((tag, key, a[key], a))
        if tag == "meta": self.meta[a.get("name", a.get("property", ""))] = a.get("content", "")
        if tag == "img" and not all(a.get(k) for k in ("alt", "width", "height")):
            self.errors.append("Image requires alt text and dimensions")
        if tag not in VOID: self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag: self.errors.append("HTML nesting mismatch")
        else: self.stack.pop()


def check(publication=False):
    errors, pages = [], {}
    if subprocess.run(["git", "check-ignore", "--quiet", ".env"], cwd=REPO,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        errors.append(".env must remain ignored and untracked")
    actual = {str(p.relative_to(SITE)) for p in SITE.rglob("*") if p.is_file()}
    if actual != ALLOWED: errors.append("Website file allowlist mismatch")
    if any(p.is_symlink() for p in SITE.rglob("*")): errors.append("Symlinks prohibited")
    # Never read unexpected output or follow a symlink outside the public root.
    if errors: return errors
    secrets = []
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                value = line.split("=", 1)[1].strip().strip("\"'")
                if len(value) >= 16: secrets.append(value.encode())
    for rel in actual:
        p = SITE / rel
        data = p.read_bytes()
        if any(s in data for s in secrets) or re.search(rb"(?:phx_|phc_|phs_|ghp_|github_pat_)[A-Za-z0-9_]{12,}", data):
            errors.append("Credential detected in public output; value suppressed")
        if p.suffix == ".html":
            page = Page(); page.feed(data.decode()); page.close(); pages[p.resolve()] = page
            errors.extend(page.errors)
            if page.stack: errors.append("Unclosed HTML elements")
            for tag in ("html", "head", "body", "title", "main", "h1"):
                if page.tags.count(tag) != 1: errors.append("Required unique semantic element missing")
            for m in ("description", "viewport", "color-scheme", "og:type", "og:site_name", "og:title", "og:description", "og:url"):
                if not page.meta.get(m): errors.append("Required page metadata missing")
            expected = BASE + (rel.removesuffix("index.html"))
            canon = [u for t,k,u,a in page.links if t == "link" and a.get("rel") == "canonical"]
            if canon != [expected] or page.meta.get("og:url") != expected: errors.append("Canonical/OG URL mismatch")
    for p, page in pages.items():
        for tag,key,url,attrs in page.links:
            parsed = urlsplit(url)
            if parsed.scheme == "mailto":
                if parsed.path != "tuhuzbayeu@gmail.com": errors.append("Unexpected email link")
                continue
            if parsed.scheme:
                if parsed.scheme != "https": errors.append("Non-HTTPS external link")
                if key == "src" or (tag == "link" and attrs.get("rel") != "canonical"):
                    errors.append("External asset dependency")
                continue
            target = (p.parent / unquote(parsed.path)).resolve() if parsed.path else p
            if target.is_dir(): target /= "index.html"
            if not target.is_relative_to(SITE.resolve()) or not target.is_file():
                errors.append("Internal link escapes public root or is missing")
            elif parsed.fragment and (target not in pages or parsed.fragment not in pages[target].ids):
                errors.append("Internal anchor missing")
    css = (SITE / "styles.css").read_text()
    if "url(" in css or "@import" in css: errors.append("CSS asset imports prohibited")
    urls = [n.text for n in ET.parse(SITE / "sitemap.xml").iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    if urls != [BASE, BASE+"privacy/", BASE+"support/"]: errors.append("Sitemap mismatch")
    robots = (SITE / "robots.txt").read_text()
    if "Sitemap: " + BASE + "sitemap.xml" not in robots or "Allow: /keep-or-skip-site/" not in robots:
        errors.append("Robots project path mismatch")
    if sum((SITE / p).stat().st_size for p in actual) > 500_000: errors.append("Static payload exceeds 500 KB budget")
    if publication:
        review = json.loads(REVIEW_FILE.read_text())
        for key in ("controller_legal_review", "retention_verified", "processor_and_transfers_verified",
                    "released_app_alignment_verified", "pages_public_repo_eligibility_verified"):
            if review.get(key) is not True: errors.append("Publication blocked: " + key)
        digest = hashlib.sha256((SITE / "privacy/index.html").read_bytes()).hexdigest()
        if review.get("approved_privacy_sha256") != digest: errors.append("Publication blocked: policy content not approved")
        if "Unpublished draft" in (SITE / "privacy/index.html").read_text(): errors.append("Draft policy cannot be deployed")
        if review.get("publishing_repository") != "tuhuzbayeu/keep-or-skip-site":
            errors.append("Publication blocked: unexpected publishing repository")
        approved = review.get("approved_public_files")
        current = {rel: hashlib.sha256((SITE / rel).read_bytes()).hexdigest() for rel in sorted(ALLOWED)}
        if approved != current: errors.append("Publication blocked: website snapshot not approved")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--publication", action="store_true")
    parser.add_argument("--review-file", type=Path, help="Review record; default is the private source record")
    args = parser.parse_args()
    if args.review_file: REVIEW_FILE = args.review_file.resolve()
    try: errors = check(args.publication)
    except Exception:
        print("Website validation failed; inspect input structure locally (details suppressed).")
        sys.exit(1)
    if errors:
        for error in sorted(set(errors)): print(error)
        sys.exit(1)
    print("PASS: 3 HTML pages; semantic structure, metadata, internal links/anchors, email, sitemap, file allowlist, credential absence and payload budget.")
