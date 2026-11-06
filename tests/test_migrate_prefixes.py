"""Data migration writes the data file's own prefixes back (#358).

Two commands migrate data: ``refactor rename --migrate-data``, which writes one output per data
file, and ``merge --migrate-data``, which combines every data file into one output and so needs
#357's rule when two of them declare one prefix differently.

Every test checks a ``@prefix`` line *and* the graph by IRI.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml
from click.testing import CliRunner, Result
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from rdf_construct.cli import cli
from tests.test_cli_smoke import assert_no_crash

if TYPE_CHECKING:
    from pathlib import Path

MYORG = "http://example.org/myorg#"
OLD = "http://old.example.org/ont#"
NEW = "http://new.example.org/ont#"
D = "http://example.org/d#"
OTHER = "http://example.org/other#"
FOAF = "http://xmlns.com/foaf/0.1/"

ONTOLOGY = f"""@prefix org: <{MYORG}> .
@prefix o: <{OLD}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

org:Team a owl:Class .
o:Building a owl:Class .
o:hasFloors a owl:DatatypeProperty .
"""

DATA = f"""@prefix org: <{MYORG}> .
@prefix o: <{OLD}> .
@prefix d: <{D}> .

d:t1 a org:Team .
d:b1 a o:Building ;
    o:hasFloors 3 .
"""

DATA2 = f"""@prefix d: <{OTHER}> .

d:x a <{MYORG}Team> .
"""


def _prefixes(text: str) -> dict[str, str]:
    return dict(re.findall(r"^@prefix ([^:\s]*): <([^>]*)> \.$", text, re.MULTILINE))


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def _run(*argv: object) -> Result:
    result = CliRunner().invoke(cli, [str(a) for a in argv])
    assert_no_crash(result)
    return result


class TestRefactorRename:
    def test_the_data_keeps_its_own_org(self, tmp_path):
        ont, data = _write(tmp_path, "ont.ttl", ONTOLOGY), _write(tmp_path, "data.ttl", DATA)
        dout = tmp_path / "dout.ttl"
        result = _run(
            "refactor", "rename", ont, "--from", "org:Team", "--to", "org:Unit",
            "-o", tmp_path / "out.ttl", "--migrate-data", data, "--data-output", dout,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        text = dout.read_text()
        assert _prefixes(text)["org"] == MYORG
        assert "org1" not in _prefixes(text)
        assert "d:t1 a org:Unit" in text
        assert (URIRef(D + "t1"), RDF.type, URIRef(MYORG + "Unit")) in Graph().parse(dout)

    def test_the_datas_prefix_moves_with_a_renamed_namespace(self, tmp_path):
        ont, data = _write(tmp_path, "ont.ttl", ONTOLOGY), _write(tmp_path, "data.ttl", DATA)
        dout = tmp_path / "dout.ttl"
        result = _run(
            "refactor", "rename", ont, "--from-namespace", OLD, "--to-namespace", NEW,
            "-o", tmp_path / "new.ttl", "--migrate-data", data, "--data-output", dout,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        text = dout.read_text()
        prefixes = _prefixes(text)
        assert prefixes["o"] == NEW
        assert OLD not in prefixes.values()
        assert not any(p.startswith("ns") for p in prefixes)
        g = Graph().parse(dout)
        assert (URIRef(D + "b1"), RDF.type, URIRef(NEW + "Building")) in g
        assert (URIRef(D + "b1"), URIRef(NEW + "hasFloors"), Literal(3)) in g

    def test_n_triples_data_gets_rdflibs_names(self, tmp_path):
        ont = _write(tmp_path, "ont.ttl", ONTOLOGY)
        data = _write(
            tmp_path,
            "people.nt",
            f"<{D}t1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{MYORG}Team> .\n"
            f'<{D}t1> <{FOAF}name> "Team one" .\n',
        )
        dout = tmp_path / "dout.ttl"
        result = _run(
            "refactor", "rename", ont, "--from", "org:Team", "--to", "org:Unit",
            "-o", tmp_path / "out.ttl", "--migrate-data", data, "--data-output", dout,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        text = dout.read_text()
        assert _prefixes(text)["foaf"] == FOAF
        g = Graph().parse(dout)
        assert (URIRef(D + "t1"), RDF.type, URIRef(MYORG + "Unit")) in g
        assert (URIRef(D + "t1"), URIRef(FOAF + "name"), Literal("Team one")) in g


class TestMergeDataMigration:
    def test_a_rename_rule_keeps_the_datas_own_org(self, tmp_path):
        ont, data = _write(tmp_path, "ont.ttl", ONTOLOGY), _write(tmp_path, "data.ttl", DATA)
        dout = tmp_path / "dout.ttl"
        config = tmp_path / "merge.yml"
        config.write_text(
            yaml.safe_dump(
                {
                    "sources": [{"path": str(ont)}],
                    "migrate_data": {
                        "sources": [str(data)],
                        "output": str(dout),
                        "rules": [{"type": "rename", "from": MYORG + "Team", "to": MYORG + "Unit"}],
                    },
                }
            )
        )
        result = _run("merge", "-c", config, "-o", tmp_path / "merged.ttl")
        assert result.exit_code == 0, result.output
        text = dout.read_text()
        assert _prefixes(text)["org"] == MYORG
        assert "org1" not in _prefixes(text)
        assert (URIRef(D + "t1"), RDF.type, URIRef(MYORG + "Unit")) in Graph().parse(dout)

    def test_two_data_files_with_one_prefix_follow_357s_rule(self, tmp_path):
        ont = _write(tmp_path, "ont.ttl", ONTOLOGY)
        data, data2 = _write(tmp_path, "data.ttl", DATA), _write(tmp_path, "data2.ttl", DATA2)
        dout = tmp_path / "dout.ttl"
        result = _run(
            "merge", ont, "-o", tmp_path / "merged.ttl",
            "--migrate-data", data, "--migrate-data", data2, "--data-output", dout,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        text = dout.read_text()
        prefixes = _prefixes(text)
        assert prefixes["d"] == D
        assert prefixes["d1"] == OTHER
        assert prefixes["org"] == MYORG
        g = Graph().parse(dout)
        assert (URIRef(OTHER + "x"), RDF.type, URIRef(MYORG + "Team")) in g
        assert (URIRef(D + "t1"), RDF.type, URIRef(MYORG + "Team")) in g
        notes = [line for line in result.stderr.splitlines() if line.startswith("Note: ")]
        assert notes == [
            f'Note: data2.ttl declares "d:" for <{OTHER}>, which data.ttl uses for <{D}>; '
            'written as "d1:".'
        ]

    @staticmethod
    def _given_name_config(tmp_path: Path, preferred: dict[str, str] | None) -> tuple[Path, Path]:
        """A merge config whose rule names foaf:, over N-Triples data that declares no prefix."""
        ont = _write(tmp_path, "ont.ttl", ONTOLOGY)
        data = _write(tmp_path, "people.nt", f'<{D}ann> <{FOAF}name> "Ann Lee" .\n')
        dout = tmp_path / "dout.ttl"
        config = tmp_path / "merge.yml"
        body: dict[str, object] = {
            "sources": [{"path": str(ont)}],
            "migrate_data": {
                "sources": [str(data)],
                "output": str(dout),
                "rules": [
                    {
                        "type": "transform",
                        "description": "given name",
                        "match": "?s foaf:name ?name",
                        "construct": [
                            {
                                "pattern": "?s foaf:givenName ?given",
                                "bind": "STRBEFORE(?name, ' ') AS ?given",
                            }
                        ],
                        "delete_matched": False,
                    }
                ],
            },
        }
        if preferred is not None:
            body["namespaces"] = {"preferred_prefixes": preferred}
        config.write_text(yaml.safe_dump(body))
        return config, dout

    def test_a_rule_curie_no_data_file_declares_is_refused(self, tmp_path):
        """Rule CURIEs resolve strictly, never through rdflib's table (#492): foaf: is refused."""
        config, dout = self._given_name_config(tmp_path, None)
        merged = tmp_path / "merged.ttl"
        result = _run("merge", "-c", config, "-o", merged)
        assert result.exit_code == 2, result.output
        assert "'foaf:name': prefix 'foaf' is not bound" in result.output
        assert not merged.exists() and not dout.exists()

    def test_a_rule_curie_resolves_through_preferred_prefixes(self, tmp_path):
        """The config's preferred_prefixes give a rule's CURIE its meaning (#492, as #357)."""
        config, dout = self._given_name_config(tmp_path, {"foaf": FOAF})
        result = _run("merge", "-c", config, "-o", tmp_path / "merged.ttl")
        assert result.exit_code == 0, result.output
        g = Graph().parse(dout)
        assert (URIRef(D + "ann"), URIRef(FOAF + "givenName"), Literal("Ann")) in g
        assert (URIRef(D + "ann"), URIRef(FOAF + "name"), Literal("Ann Lee")) in g
        assert not any(str(p).startswith("foaf:") for p in g.predicates())
