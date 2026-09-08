# Ordering examples

Material for the [Order Guide](../../docs/user_guides/ORDER_GUIDE.md). Every command in that guide
runs verbatim, from the repository root, against the files here.

| File | What it is |
|---|---|
| `library.ttl` | A 57-triple ontology built so that alphabetical and hierarchical order visibly **disagree** — every class sorts before its own parent. It carries one term of each kind the selectors distinguish, including a property declared only by an OWL characteristic and one whose kind cannot be inferred. |
| `ordering.yml` | The configuration the guide uses. **Every key in it is one the tool actually reads.** Five profiles: `alpha`, `hierarchy`, `anchored`, `schema-only` and `classes-only`. |

## Try it

```bash
rdf-construct profiles examples/order/ordering.yml
rdf-construct order examples/order/library.ttl examples/order/ordering.yml
```

Five files appear in `ordered/`. Compare the class order in `library-alpha.ttl` against
`library-hierarchy.ttl`: the first lists `Anthology` before `Work`, the second lists `Work` first.

## The other files here

`sample_profile.yml`, `ies_profile.yml` and `test_profile.yml` predate the guide and are kept
because the test suite uses two of them. **They are not a model to copy**: between them they carry
eleven configuration keys that are parsed and never read, which is why two of `sample_profile.yml`'s
four profiles produce output byte-identical to the other two. See
[#243](https://github.com/aigora-de/rdf-construct/issues/243).

`basic_ordering.py` does not run — see
[#244](https://github.com/aigora-de/rdf-construct/issues/244). The Order Guide carries a working
programmatic example in the meantime.
