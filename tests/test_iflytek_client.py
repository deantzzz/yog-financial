from __future__ import annotations

import base64
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx

from backend.infrastructure.iflytek import IFlyTekOCRClient


def _encode_payload(data: dict) -> str:
    return base64.b64encode(json.dumps(data).encode("utf-8")).decode("ascii")


def test_extract_text_parses_tables(tmp_path, monkeypatch):
    table = {
        "type": "table",
        "cells": [
            {"row": 0, "col": 0, "content": [[{"type": "textline", "text": "姓名"}]]},
            {"row": 0, "col": 1, "content": [[{"type": "textline", "text": "金额"}]]},
            {"row": 1, "col": 0, "content": [[{"type": "textline", "text": "张三"}]]},
            {"row": 1, "col": 1, "content": [[{"type": "textline", "text": "100"}]]},
        ],
    }
    structured = {"type": "document", "content": [[table]]}
    encoded = _encode_payload(structured)

    response_body = {
        "header": {"code": 0, "message": "success", "sid": "demo-sid", "status": 0},
        "payload": {
            "result": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "json",
                "status": 2,
                "seq": 0,
                "text": encoded,
            }
        },
    }

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        assert request.url.params["authorization"] == "AUTH"
        assert request.url.params["host"] == "cbm01.cn-huabei-1.xf-yun.com"
        assert request.url.params["date"] == "Wed, 11 Aug 2021 06:55:18 GMT"
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)

    client = IFlyTekOCRClient("appid", "apikey", "secret", http_client=http_client)
    monkeypatch.setattr(
        client,
        "_build_auth_query",
        lambda: {
            "authorization": "AUTH",
            "host": "cbm01.cn-huabei-1.xf-yun.com",
            "date": "Wed, 11 Aug 2021 06:55:18 GMT",
        },
    )

    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    result = client.extract_text(image_path)

    assert "authorization=AUTH" in captured["url"]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["header"]["app_id"] == "appid"
    assert body["payload"]["image"]["encoding"] == "png"

    assert result.text.strip().startswith("{")
    assert result.metadata["provider"] == "iflytek"
    assert result.metadata["sid"] == "demo-sid"
    assert result.metadata["tables"] == [["姓名", "金额"], ["张三", "100"]]
    assert result.metadata["raw"] == structured

    client.close()
    http_client.close()


def test_extract_text_deduplicates_cell_content(tmp_path, monkeypatch):
    structured = {
        "type": "document",
        "content": [
            [
                {
                    "type": "table",
                    "cells": [
                        {
                            "row": 0,
                            "col": 0,
                            "text": "2025年",
                            "words": [
                                {"text": "2025年"},
                                {"text": "2025年"},
                            ],
                        }
                    ],
                }
            ]
        ],
    }
    encoded = _encode_payload(structured)

    response_body = {
        "header": {"code": 0, "message": "success", "status": 0},
        "payload": {
            "result": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "json",
                "status": 2,
                "seq": 0,
                "text": encoded,
            }
        },
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)

    client = IFlyTekOCRClient("appid", "apikey", "secret", http_client=http_client)
    monkeypatch.setattr(
        client,
        "_build_auth_query",
        lambda: {"authorization": "AUTH", "host": "cbm01.cn-huabei-1.xf-yun.com", "date": "Wed, 11 Aug 2021 06:55:18 GMT"},
    )

    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"\xff\xd8\xff")

    result = client.extract_text(image_path)

    assert result.metadata["tables"] == [["2025年"]]

    client.close()
    http_client.close()
