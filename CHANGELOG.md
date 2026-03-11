# Changelog

## [1.0.0](https://github.com/vexxhost/entra-pim-mcp-server/compare/v0.1.0...v1.0.0) (2026-03-11)


### ⚠ BREAKING CHANGES

* AZURE_CLIENT_ID environment variable is no longer used. Remove it from your configuration.

### Features

* use Microsoft Graph PowerShell well-known client ID ([f81ac29](https://github.com/vexxhost/entra-pim-mcp-server/commit/f81ac298e847f0274501cbc03a9f1396ce8679e4))


### Documentation

* update examples to use PyPI package directly ([744edde](https://github.com/vexxhost/entra-pim-mcp-server/commit/744edde899ea4f7be9027b0dade7c27034662a38))

## 0.1.0 (2026-03-11)


### Features

* **auth:** add Azure authentication with token cache persistence ([d47e42c](https://github.com/vexxhost/entra-pim-mcp-server/commit/d47e42cbee7b4f63368e8ff9ef4e707a88def214))
* initialize Python project with uv and MCP stub server ([3f2be9b](https://github.com/vexxhost/entra-pim-mcp-server/commit/3f2be9b82e49974b3fcb2938e8df0dc141bbf8d1))
* **tools:** add activate MCP tool with policy lookup ([4beb177](https://github.com/vexxhost/entra-pim-mcp-server/commit/4beb177c79819b2762fb7d3f6d5eada271291d1c))
* **tools:** add list_eligible MCP tool ([658febd](https://github.com/vexxhost/entra-pim-mcp-server/commit/658febd930c23ac07536457fcca84a8d57657a8e))
* **tools:** add structured output, titles, and parameter metadata ([6746550](https://github.com/vexxhost/entra-pim-mcp-server/commit/6746550905b6b88c8cea82ea878993a9dc8a66a0))


### Bug Fixes

* **activate:** correct accessId lookup, null checks, and duration warnings ([13828ae](https://github.com/vexxhost/entra-pim-mcp-server/commit/13828aefefce5c8ef0441161847c7f25a2717236))
* **activate:** fix duration serialization and add startDateTime ([723e68e](https://github.com/vexxhost/entra-pim-mcp-server/commit/723e68e209e3cba8dbc421aa946386c8566cafe9))
* **activate:** use access_id from eligibility instead of parameter ([19ed131](https://github.com/vexxhost/entra-pim-mcp-server/commit/19ed131f6630f13da8a3fecbff471f52703e893e))
* **auth:** add port to redirect_uri for browser credential ([bb9df21](https://github.com/vexxhost/entra-pim-mcp-server/commit/bb9df21d3c6cbb7938f6021272e75860b0a41aa2))
* **auth:** skip explicit authenticate() when auth record exists ([e1b7a91](https://github.com/vexxhost/entra-pim-mcp-server/commit/e1b7a91210e8b14ee00758e19a05da81e2dbd235))
* rename tool titles from Title Case to normal casing ([e41ec46](https://github.com/vexxhost/entra-pim-mcp-server/commit/e41ec46819512f604c27deb136864195b5836494))
* resolve Pylance type errors in server.py ([b740be9](https://github.com/vexxhost/entra-pim-mcp-server/commit/b740be9b7131960d0577415d00265e0b06d3b362))
* use sentence case for tool titles ([b03ac03](https://github.com/vexxhost/entra-pim-mcp-server/commit/b03ac038aa4671a919f0ebe2dfc54bf5ae7cc85d))


### Documentation

* add Python rewrite design spec ([fcf9e4a](https://github.com/vexxhost/entra-pim-mcp-server/commit/fcf9e4a61b7e62d94f1c9f7de296babd9ece2f67))
* add Python rewrite implementation plan ([1f65ce0](https://github.com/vexxhost/entra-pim-mcp-server/commit/1f65ce064de43a5d15baf89dcc030134f1b28836))
* rewrite README for Python/uvx usage ([40e53cd](https://github.com/vexxhost/entra-pim-mcp-server/commit/40e53cd36c99b1f1dc906283d0f039f7413b5eb0))
