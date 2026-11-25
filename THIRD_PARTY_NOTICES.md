# Third-party notices

Garmin Stats for Claude is MIT licensed (see LICENSE). It builds on the open-source
projects below. Each keeps its own licence; their licence texts ship inside the
installed packages. This list is generated from the runtime dependencies of v0.2.0.

## Tools used by the installer (not bundled)

| Project | Licence | |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) | MIT OR Apache-2.0 | installs the helper and a private Python |
| [Python](https://www.python.org) | PSF-2.0 | runtime, downloaded by uv |

## Python packages installed with the helper

| Package | Version | Licence |
|---|---|---|
| [annotated-types](https://github.com/annotated-types/annotated-types) | 0.8.0 | MIT |
| [anyio](https://github.com/agronholm/anyio) | 4.16.0 | MIT |
| [attrs](https://github.com/python-attrs/attrs) | 26.1.0 | MIT |
| [certifi](https://github.com/certifi/python-certifi) | 2026.11.20 | Mozilla Public License 2.0 (MPL 2.0) |
| [cffi](https://github.com/python-cffi/cffi) | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.3 | MIT |
| [click](https://github.com/pallets/click/) | 8.5.1 | BSD-3-Clause |
| [cryptography](https://github.com/pyca/cryptography) | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) | 0.17.0 | MIT |
| [garminconnect](https://github.com/cyberjunky/python-garminconnect) | 0.3.20 | MIT License |
| [h11](https://github.com/python-hyper/h11) | 0.16.0 | MIT License |
| [httpcore](https://www.encode.io/httpcore/) | 1.0.9 | BSD-3-Clause |
| [httpx](https://github.com/encode/httpx) | 0.28.1 | BSD License |
| [httpx-sse](https://github.com/florimondmanca/httpx-sse) | 0.4.3 | MIT |
| [idna](https://github.com/kjd/idna) | 3.20 | BSD-3-Clause |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | 4.26.0 | MIT |
| [jsonschema-specifications](https://github.com/python-jsonschema/jsonschema-specifications) | 2025.9.1 | MIT |
| [mcp](https://modelcontextprotocol.io) | 1.30.0 | MIT License |
| [pycparser](https://github.com/eliben/pycparser) | 3.12 | BSD-3-Clause |
| [pydantic](https://github.com/pydantic/pydantic) | 2.14.4 | MIT |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.16.3 | MIT |
| [pydantic_core](https://github.com/pydantic/pydantic) | 2.50.5 | MIT |
| [PyJWT](https://github.com/jpadilla/pyjwt) | 2.15.1 | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.4 | BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.34 | Apache-2.0 |
| [referencing](https://github.com/python-jsonschema/referencing) | 0.37.0 | MIT |
| [requests](https://github.com/psf/requests) | 2.34.2 | Apache Software License |
| [rpds-py](https://github.com/crate-py/rpds) | 2026.9.1 | MIT |
| [sse-starlette](https://github.com/sysid/sse-starlette) | 3.7.1 | BSD-3-Clause |
| [starlette](https://github.com/Kludex/starlette) | 1.10.0 | BSD-3-Clause |
| [typing-inspection](https://github.com/pydantic/typing-inspection) | 0.4.5 | MIT |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF-2.0 |
| [ua-generator](https://github.com/iamdual/ua-generator) | 2.1.9 | Apache Software License |
| urllib3 | 2.8.0 | MIT |
| [uvicorn](https://uvicorn.dev/) | 0.54.0 | BSD-3-Clause |

curl_cffi bundles [curl-impersonate](https://github.com/lexiforest/curl-impersonate) (MIT) and
[libcurl](https://curl.se/docs/copyright.html) (curl licence, MIT-style).
