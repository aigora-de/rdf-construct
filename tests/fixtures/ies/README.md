# Pinned IES ontologies

Three ontologies from the UK Government's
[Information Exchange Standard (IES)](https://github.com/IES-Org), committed **verbatim** as
realistic test material ([#307](https://github.com/aigora-de/rdf-construct/issues/307)). Every
other fixture in this repository was written for rdf-construct. These were not, which is their
whole value. Do not trim, reformat or re-serialise them. To move to a newer upstream version,
replace a file wholesale and update its row here and its pin in `tests/test_ies_fixtures.py`.

| File | Repository | Path | Commit | `owl:versionInfo` |
|---|---|---|---|---|
| `ies-common.ttl` | [`IES-Org/ont-ies`](https://github.com/IES-Org/ont-ies) | `docs/specification/ies-common.ttl` | [`3f38568b79b1058433ace2c94e6cff870a8e66ad`](https://github.com/IES-Org/ont-ies/blob/3f38568b79b1058433ace2c94e6cff870a8e66ad/docs/specification/ies-common.ttl) | 5.0.3 |
| `ies-env-building.ttl` | [`IES-Org/ies-env-building`](https://github.com/IES-Org/ies-env-building) | `specification/ontology/ies-env-building.ttl` | [`02c3a707c53d4d29784689842843ea87299ff4f1`](https://github.com/IES-Org/ies-env-building/blob/02c3a707c53d4d29784689842843ea87299ff4f1/specification/ontology/ies-env-building.ttl) | 1.0.0 (`building:`); 0.1.0-rc1 (`env:`) |
| `ies-env-building-classification.ttl` | [`IES-Org/ies-env-building`](https://github.com/IES-Org/ies-env-building) | `specification/ontology/ies-env-building-classification.ttl` | [`02c3a707c53d4d29784689842843ea87299ff4f1`](https://github.com/IES-Org/ies-env-building/blob/02c3a707c53d4d29784689842843ea87299ff4f1/specification/ontology/ies-env-building-classification.ttl) | 1.0.0 |

`tests/test_ies_fixtures.py` checks each file's git blob SHA against the pinned commit, its
`owl:Ontology` headers and their `owl:versionInfo`. A silent swap, a trim or a whitespace rewrite
fails the suite. `.gitattributes` keeps line endings unconverted on checkout, and
`.pre-commit-config.yaml` excludes this directory from the hooks that rewrite whitespace.

## What they are for

- **The release checklist:** every command is run over all three before a tag (see
  `CONTRIBUTING.md`, Release Process).
- **`ies-env-building.ttl` references `ies:common` terms it does not define**, so `lint` reports
  them as dangling references
  ([#69](https://github.com/aigora-de/rdf-construct/issues/69)).
- **`ies-env-building.ttl` declares two `owl:Ontology` headers**
  ([#90](https://github.com/aigora-de/rdf-construct/issues/90),
  [#171](https://github.com/aigora-de/rdf-construct/issues/171),
  [#178](https://github.com/aigora-de/rdf-construct/issues/178)).
- A realistic size for timing the topological sort
  ([#300](https://github.com/aigora-de/rdf-construct/issues/300)), and the committed fixture
  that UML ancestor selection needs ([#44](https://github.com/aigora-de/rdf-construct/issues/44)).

## Licence

Both source repositories license their code under the MIT Licence and their documentation under
the Open Government Licence v3.0. These files are code: the `ont-ies` commit pinned above is
"fix(license): correct spec files to MIT Licence", and `ies-common.ttl` carries the MIT notice in
its own header. The MIT Licence requires the copyright and permission notice below to travel with
the copies. It is reproduced from the `LICENSE.md` of both repositories at the pinned commits.

> © Crown Copyright 2026. This work forms part of the Information Exchange Standard initiative and
> is currently under the custodianship of the Department for Business and Trade (UK), acting on
> behalf of a cross-government group of stakeholders. This code is licensed under the MIT License.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software
> and associated documentation files (the “Software”), to deal in the Software without
> restriction, including without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
> Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
> BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
> DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

These files are not covered by rdf-construct's own `LICENSE`. Copyright in them remains with the
Crown.
