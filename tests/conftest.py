"""Shared fixtures: a fake google-genai client and a fake `types` module.

The real SDK is never imported in tests. We inject a lightweight stand-in into
``sys.modules`` as ``google.genai`` so the lazily-imported production code picks
it up. This keeps tests fast, offline, and free of API keys.
"""
import sys
import types as pytypes

import pytest


class _Part:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    @classmethod
    def from_uri(cls, file_uri, mime_type):
        return cls(file_uri=file_uri, mime_type=mime_type)

    @classmethod
    def from_text(cls, text):
        return cls(text=text)


class _Content:
    def __init__(self, role="user", parts=None):
        self.role = role
        self.parts = parts or []


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture(autouse=True)
def fake_genai(monkeypatch):
    """Install a fake `google.genai` + `google.genai.types` for the test run."""
    google_mod = pytypes.ModuleType("google")
    genai_mod = pytypes.ModuleType("google.genai")
    types_mod = pytypes.ModuleType("google.genai.types")

    types_mod.Part = _Part
    types_mod.Content = _Content
    types_mod.CreateCachedContentConfig = _Cfg
    types_mod.UpdateCachedContentConfig = _Cfg
    types_mod.GenerateContentConfig = _Cfg

    genai_mod.types = types_mod
    genai_mod.Client = lambda **kw: FakeClient()
    google_mod.genai = genai_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)
    yield


class FakeUsage:
    def __init__(self, prompt=0, cached=0, output=0, total=0):
        self.prompt_token_count = prompt
        self.cached_content_token_count = cached
        self.candidates_token_count = output
        self.total_token_count = total


class FakeResponse:
    def __init__(self, text, usage):
        self.text = text
        self.usage_metadata = usage


class FakeCache:
    def __init__(self, name="cachedContents/test123", tokens=5000):
        self.name = name
        self.usage_metadata = FakeUsage(total=tokens)
        self.create_time = None
        self.expire_time = None


class FakeFiles:
    def upload(self, file, config=None):
        return pytypes.SimpleNamespace(
            name="files/abc", uri="https://gen.example/files/abc"
        )


class FakeCaches:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, model, config):
        self.created.append((model, config))
        return FakeCache()

    def get(self, name):
        return FakeCache(name=name)

    def update(self, name, config):
        return FakeCache(name=name)

    def delete(self, name):
        self.deleted.append(name)


class FakeModels:
    def __init__(self):
        # cached call returns mostly-cached usage; full-context returns all-fresh
        self.responses = []

    def generate_content(self, model, contents, config=None):
        if config is not None and getattr(config, "cached_content", None):
            usage = FakeUsage(prompt=5200, cached=5000, output=120, total=5320)
            return FakeResponse("Cached answer.", usage)
        usage = FakeUsage(prompt=5200, cached=0, output=120, total=5320)
        return FakeResponse("Full-context answer.", usage)

    def generate_content_stream(self, model, contents, config=None):
        for chunk in ["Hello ", "world"]:
            yield pytypes.SimpleNamespace(text=chunk)


class FakeClient:
    def __init__(self):
        self.files = FakeFiles()
        self.caches = FakeCaches()
        self.models = FakeModels()


@pytest.fixture
def client():
    return FakeClient()
