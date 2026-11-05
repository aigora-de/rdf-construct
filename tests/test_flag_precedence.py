"""Tests for flag-versus-config precedence (#160, #206, #225, #251, #351).

Decided on #160: an option given on the command line overrides the config file, and the
config file overrides the option's default. Click fills in a default whenever a flag is
absent, so each command applies an option over its config only when ``flag_given`` says the
user supplied it.

Every key is run three ways:

1. the config sets it and the flag is absent, so the config wins;
2. the flag is given, so the flag wins;
3. the flag is given explicitly at its own default, so the flag still wins. This is the case
   that tells "given" apart from "differs from the default".

Case 3 does not exist for an ``is_flag`` option such as ``--no-search``, because passing it
can only set it, and nor for an option with no default, such as ``--properties``.

Each fixture makes a wrong answer visible in what the command wrote or how it exited, not
only in a config object.
"""

from pathlib import Path
from typing import Any

import click
import pytest
import yaml
from click.testing import CliRunner
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

from rdf_construct.cli import cli, flag_given
from rdf_construct.shacl import SH

REPO = Path(__file__).parent.parent
DOCS_FIXTURE = REPO / "tests" / "fixtures" / "docs" / "deprecated_terms.ttl"
MERGE_LABELS = REPO / "tests" / "fixtures" / "merge" / "conflicts"

# One class with no superclass: orphan-class is a warning at standard and an error at
# strict, so the level shows up in the exit code.
LINT_ONTOLOGY = """\
@prefix ex: <http://example.org/w#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex: a owl:Ontology ; rdfs:label "W" ; rdfs:comment "W" .
ex:Thing a owl:Class ; rdfs:label "Thing" ; rdfs:comment "A thing." .
"""

# owl:oneOf becomes sh:in from standard up (#227); not at minimal.
ENUM_ONTOLOGY = """\
@prefix ex: <http://example.org/enum#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex: a owl:Ontology .
ex:Colour a owl:Class ; owl:oneOf ( ex:Red ex:Green ) .
ex:Car a owl:Class .
ex:hasColour a owl:ObjectProperty ; rdfs:domain ex:Car ; rdfs:range ex:Colour .
"""

# Done already has a German label, Todo does not, and Old is deprecated. Every label also
# exists in French, so the source language shows up in the extracted strings.
LOCALISE_ONTOLOGY = """\
@prefix ex: <http://example.org/loc#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Done a owl:Class ;
    rdfs:label "Done"@en , "Fait"@fr , "Erledigt"@de ;
    rdfs:comment "Already translated."@en .
ex:Todo a owl:Class ;
    rdfs:label "Todo"@en , "A faire"@fr ;
    rdfs:comment "Not yet translated."@en .
ex:Old a owl:Class ; owl:deprecated true ; rdfs:label "Old"@en , "Vieux"@fr .
"""

RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in a scratch directory, so nothing defaulted lands in the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


class TestFlagGiven:
    """The helper itself, on a throwaway command."""

    @staticmethod
    def probe(**option_kwargs: Any) -> click.Command:
        @click.command()
        @click.option("--level", default="standard", **option_kwargs)
        def command(level: str) -> None:
            click.echo(f"given={flag_given('level')}")

        return command

    def test_absent_is_not_given(self, runner: CliRunner) -> None:
        result = runner.invoke(self.probe(), [])
        assert result.output.strip() == "given=False"

    def test_given_at_its_default_is_given(self, runner: CliRunner) -> None:
        result = runner.invoke(self.probe(), ["--level", "standard"])
        assert result.output.strip() == "given=True"

    def test_the_environment_counts_as_given(self, runner: CliRunner) -> None:
        result = runner.invoke(
            self.probe(envvar="PROBE_LEVEL"), [], env={"PROBE_LEVEL": "standard"}
        )
        assert result.output.strip() == "given=True"

    def test_a_default_map_is_not_given(self, runner: CliRunner) -> None:
        result = runner.invoke(self.probe(), [], default_map={"level": "strict"})
        assert result.output.strip() == "given=False"

    def test_an_unknown_name_raises(self, runner: CliRunner) -> None:
        @click.command()
        def command() -> None:
            flag_given("levle")

        result = runner.invoke(command, [])
        assert isinstance(result.exception, LookupError)
        assert "levle" in str(result.exception)


class TestLintLevel:
    """#206: ``level:`` in a lint config, explicit or auto-discovered."""

    @pytest.fixture
    def source(self, cwd: Path) -> Path:
        path = cwd / "ontology.ttl"
        path.write_text(LINT_ONTOLOGY, encoding="utf-8")
        return path

    def test_explicit_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, cwd: Path, source: Path
    ) -> None:
        config = write_yaml(cwd / "strict.yml", {"level": "strict"})
        result = runner.invoke(cli, ["lint", "-c", str(config), str(source)])
        assert result.exit_code == 1, result.output
        assert "Found 1 error, 0 warnings" in result.output

    def test_discovered_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, cwd: Path, source: Path
    ) -> None:
        write_yaml(cwd / ".rdf-lint.yml", {"level": "strict"})
        result = runner.invoke(cli, ["lint", str(source)])
        assert "Using config:" in result.output
        assert result.exit_code == 1, result.output
        assert "Found 1 error, 0 warnings" in result.output

    def test_the_flag_wins_when_given(self, runner: CliRunner, cwd: Path, source: Path) -> None:
        config = write_yaml(cwd / "standard.yml", {"level": "standard"})
        result = runner.invoke(cli, ["lint", "-c", str(config), "--level", "strict", str(source)])
        assert result.exit_code == 1, result.output
        assert "Found 1 error, 0 warnings" in result.output

    def test_the_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, cwd: Path, source: Path
    ) -> None:
        write_yaml(cwd / ".rdf-lint.yml", {"level": "strict"})
        result = runner.invoke(cli, ["lint", "--level", "standard", str(source)])
        assert result.exit_code == 0, result.output
        assert "Found 0 errors, 1 warning" in result.output


class TestShaclGen:
    """#225: ``level:`` and ``default_severity:`` in a shacl-gen config."""

    @pytest.fixture
    def source(self, tmp_path: Path) -> Path:
        path = tmp_path / "enum.ttl"
        path.write_text(ENUM_ONTOLOGY, encoding="utf-8")
        return path

    def run(self, runner: CliRunner, source: Path, config: Path, *flags: str) -> Graph:
        output = source.parent / "shapes.ttl"
        result = runner.invoke(
            cli, ["shacl-gen", str(source), "--config", str(config), "-o", str(output), *flags]
        )
        assert result.exit_code == 0, result.output
        return Graph().parse(output)

    @staticmethod
    def has_sh_in(shapes: Graph) -> bool:
        return (None, SH["in"], None) in shapes

    # level: since #227, sh:in appears from standard up, so minimal against standard is the
    # pair a wrong answer shows in (strict is an alias of standard).

    def test_level_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"level": "minimal"})
        assert not self.has_sh_in(self.run(runner, source, config))

    def test_level_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"level": "standard"})
        assert not self.has_sh_in(self.run(runner, source, config, "--level", "minimal"))

    def test_level_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"level": "minimal"})
        assert self.has_sh_in(self.run(runner, source, config, "--level", "standard"))

    # default_severity: read from what was written, sh:severity on every shape (#223)

    @pytest.mark.parametrize(
        ("flags", "expected"),
        [
            ((), SH.Warning),
            (("--default-severity", "info"), SH.Info),
            (("--default-severity", "violation"), SH.Violation),
        ],
        ids=["config-wins-when-absent", "flag-wins", "flag-wins-at-its-default"],
    )
    def test_default_severity_is_written(
        self,
        runner: CliRunner,
        tmp_path: Path,
        source: Path,
        flags: tuple[str, ...],
        expected: URIRef,
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"default_severity": "warning"})
        shapes = self.run(runner, source, config, *flags)
        assert set(shapes.objects(None, SH.severity)) == {expected}


class TestDocs:
    """#251: the seven ``docs`` keys that CLI defaults used to overwrite."""

    def run(self, runner: CliRunner, config: Path, *flags: str) -> None:
        result = runner.invoke(cli, ["docs", str(DOCS_FIXTURE), "-C", str(config), *flags])
        assert result.exit_code == 0, result.output

    # output_dir. Run in tmp_path, so the default `docs/` would land there visibly.

    def test_output_dir_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, cwd: Path
    ) -> None:
        config = write_yaml(cwd / "c.yml", {"output_dir": str(cwd / "from_config")})
        self.run(runner, config)
        assert (cwd / "from_config" / "index.html").is_file()
        assert not (cwd / "docs").exists()

    def test_output_dir_flag_wins_when_given(self, runner: CliRunner, cwd: Path) -> None:
        config = write_yaml(cwd / "c.yml", {"output_dir": str(cwd / "from_config")})
        self.run(runner, config, "-o", str(cwd / "from_flag"))
        assert (cwd / "from_flag" / "index.html").is_file()
        assert not (cwd / "from_config").exists()

    def test_output_dir_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, cwd: Path
    ) -> None:
        config = write_yaml(cwd / "c.yml", {"output_dir": str(cwd / "from_config")})
        self.run(runner, config, "-o", "docs")
        assert (cwd / "docs" / "index.html").is_file()
        assert not (cwd / "from_config").exists()

    # format

    def test_format_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"format": "markdown"})
        self.run(runner, config, "-o", str(tmp_path / "out"))
        assert (tmp_path / "out" / "index.md").is_file()
        assert not (tmp_path / "out" / "index.html").exists()

    def test_format_flag_wins_when_given(self, runner: CliRunner, tmp_path: Path) -> None:
        config = write_yaml(tmp_path / "c.yml", {"format": "html"})
        self.run(runner, config, "-o", str(tmp_path / "out"), "-f", "md")
        assert (tmp_path / "out" / "index.md").is_file()
        assert not (tmp_path / "out" / "index.html").exists()

    def test_format_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"format": "markdown"})
        self.run(runner, config, "-o", str(tmp_path / "out"), "-f", "html")
        assert (tmp_path / "out" / "index.html").is_file()
        assert not (tmp_path / "out" / "index.md").exists()

    # single_page: a multi-page site writes classes/, a single page does not.

    def test_single_page_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {"single_page": True})
        self.run(runner, config, "-o", str(tmp_path / "out"))
        assert (tmp_path / "out" / "index.html").is_file()
        assert not (tmp_path / "out" / "classes").exists()

    def test_single_page_flag_wins_when_given(self, runner: CliRunner, tmp_path: Path) -> None:
        config = write_yaml(tmp_path / "c.yml", {"single_page": False})
        self.run(runner, config, "-o", str(tmp_path / "out"), "--single-page")
        assert (tmp_path / "out" / "index.html").is_file()
        assert not (tmp_path / "out" / "classes").exists()

    # The four exclusions. Each one's output is a path written or not written.

    EXCLUSIONS = [
        ("include_search", "--no-search", "search.json"),
        ("include_instances", "--no-instances", "instances"),
        ("include_shapes", "--no-shapes", "shapes"),
        ("include_skos", "--no-skos", "concepts"),
    ]
    EXCLUSION_IDS = [key for key, _, _ in EXCLUSIONS]

    @pytest.mark.parametrize(("key", "flag", "written"), EXCLUSIONS, ids=EXCLUSION_IDS)
    def test_exclusion_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, key: str, flag: str, written: str
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {key: False})
        self.run(runner, config, "-o", str(tmp_path / "out"))
        assert (tmp_path / "out" / "index.html").is_file()
        assert not (tmp_path / "out" / written).exists()

    @pytest.mark.parametrize(("key", "flag", "written"), EXCLUSIONS, ids=EXCLUSION_IDS)
    def test_exclusion_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, key: str, flag: str, written: str
    ) -> None:
        config = write_yaml(tmp_path / "c.yml", {key: True})
        self.run(runner, config, "-o", str(tmp_path / "out"), flag)
        assert (tmp_path / "out" / "index.html").is_file()
        assert not (tmp_path / "out" / written).exists()

    @pytest.mark.parametrize(("key", "flag", "written"), EXCLUSIONS, ids=EXCLUSION_IDS)
    def test_exclusion_absent_from_both_still_writes(
        self, runner: CliRunner, tmp_path: Path, key: str, flag: str, written: str
    ) -> None:
        """The control: the fixture really does produce each path the tests above look for."""
        config = write_yaml(tmp_path / "c.yml", {"title": "Control"})
        self.run(runner, config, "-o", str(tmp_path / "out"))
        assert (tmp_path / "out" / written).exists()


class TestLocaliseExtract:
    """#160: with ``-c``, the four extraction flags were discarded."""

    @pytest.fixture
    def source(self, tmp_path: Path) -> Path:
        path = tmp_path / "ontology.ttl"
        path.write_text(LOCALISE_ONTOLOGY, encoding="utf-8")
        return path

    @staticmethod
    def config(tmp_path: Path, *, source: str = "en", **extract: Any) -> Path:
        return write_yaml(
            tmp_path / "localise.yml",
            {
                "localise": {
                    "properties": [RDFS_LABEL],
                    "languages": {"source": source},
                    "extract": extract,
                }
            },
        )

    def run(self, runner: CliRunner, source: Path, config: Path, *flags: str) -> dict[str, Any]:
        output = source.parent / "de.yml"
        result = runner.invoke(
            cli,
            ["localise", "extract", str(source), "-l", "de", "-c", str(config)]
            + ["-o", str(output), *flags],
        )
        assert result.exit_code == 0, result.output
        written: dict[str, Any] = yaml.safe_load(output.read_text(encoding="utf-8"))
        return written

    @staticmethod
    def entities(written: dict[str, Any]) -> set[str]:
        return {e["uri"].rsplit("#", 1)[1] for e in written["entities"]}

    @staticmethod
    def sources(written: dict[str, Any]) -> set[str]:
        return {label["source"] for e in written["entities"] for label in e["labels"]}

    # source_language. The strings themselves are checked, not only the metadata, because
    # the old failure recorded English strings as English while French had been asked for.

    def test_source_language_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(runner, source, self.config(tmp_path, source="fr"))
        assert written["metadata"]["source_language"] == "fr"
        assert "A faire" in self.sources(written)

    def test_source_language_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(
            runner, source, self.config(tmp_path, source="en"), "--source-language", "fr"
        )
        assert written["metadata"]["source_language"] == "fr"
        assert "A faire" in self.sources(written)
        assert "Todo" not in self.sources(written)

    def test_source_language_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(
            runner, source, self.config(tmp_path, source="fr"), "--source-language", "en"
        )
        assert written["metadata"]["source_language"] == "en"
        assert "Todo" in self.sources(written)
        assert "A faire" not in self.sources(written)

    # properties

    def test_properties_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(runner, source, self.config(tmp_path))
        assert written["metadata"]["properties"] == ["rdfs:label"]

    def test_properties_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(runner, source, self.config(tmp_path), "-p", "rdfs:comment")
        assert written["metadata"]["properties"] == ["rdfs:comment"]
        assert "Not yet translated." in self.sources(written)

    # missing_only: Done already has a German label.

    def test_missing_only_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(runner, source, self.config(tmp_path, missing_only=True))
        assert "Done" not in self.entities(written)
        assert "Todo" in self.entities(written)

    def test_missing_only_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(
            runner, source, self.config(tmp_path, missing_only=False), "--missing-only"
        )
        assert "Done" not in self.entities(written)
        assert "Todo" in self.entities(written)

    # include_deprecated: Old is owl:deprecated.

    def test_include_deprecated_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(runner, source, self.config(tmp_path, include_deprecated=True))
        assert "Old" in self.entities(written)

    def test_include_deprecated_flag_wins_when_given(
        self, runner: CliRunner, tmp_path: Path, source: Path
    ) -> None:
        written = self.run(
            runner,
            source,
            self.config(tmp_path, include_deprecated=False),
            "--include-deprecated",
        )
        assert "Old" in self.entities(written)

    def test_the_issue_reproducer(self, runner: CliRunner, tmp_path: Path, source: Path) -> None:
        """#160's own command line: every flag given alongside ``-c`` takes effect."""
        written = self.run(
            runner,
            source,
            self.config(tmp_path),
            "-p",
            "rdfs:label",
            "--missing-only",
            "--source-language",
            "fr",
        )
        assert written["metadata"]["source_language"] == "fr"
        assert self.entities(written) == {"Todo"}
        assert self.sources(written) == {"A faire"}


class TestMerge:
    """``merge -c`` (#351): ``--strategy``, ``--imports``, ``-p``, ``--migrate-data`` and
    ``--data-output`` were all discarded whenever a config was given.

    The three ``labels_*`` sources give ``ex:Thing`` the English labels Alpha, Beta and Gamma.
    With priorities a=1, b=3, c=2, ``first`` keeps Alpha, ``priority`` keeps Beta and ``last``
    keeps Gamma, so every outcome names the strategy that produced it.
    """

    THING = URIRef("http://example.org/Thing")
    IMPORTED = URIRef("http://example.org/other")

    @staticmethod
    def config(tmp_path: Path, **extra: Any) -> Path:
        data: dict[str, Any] = {
            "sources": [
                {"path": str(MERGE_LABELS / "labels_a.ttl"), "priority": 1},
                {"path": str(MERGE_LABELS / "labels_b.ttl"), "priority": 3},
                {"path": str(MERGE_LABELS / "labels_c.ttl"), "priority": 2},
            ],
            **extra,
        }
        return write_yaml(tmp_path / "merge.yml", data)

    @staticmethod
    def run(
        runner: CliRunner, tmp_path: Path, config: Path, *args: str, exit_code: int = 0
    ) -> Graph:
        out = tmp_path / "merged.ttl"
        result = runner.invoke(cli, ["merge", "-c", str(config), "-o", str(out), *args])
        assert result.exit_code == exit_code, result.output
        return Graph().parse(out)

    def english(self, graph: Graph) -> set[str]:
        return {
            str(label)
            for label in graph.objects(self.THING, RDFS.label)
            if getattr(label, "language", None) == "en"
        }

    # strategy: config first (Alpha), flag last (Gamma), default priority (Beta).

    def test_strategy_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        merged = self.run(runner, tmp_path, self.config(tmp_path, conflicts={"strategy": "first"}))
        assert self.english(merged) == {"Alpha"}

    def test_strategy_flag_wins_when_given(self, runner: CliRunner, tmp_path: Path) -> None:
        config = self.config(tmp_path, conflicts={"strategy": "first"})
        merged = self.run(runner, tmp_path, config, "--strategy", "last")
        assert self.english(merged) == {"Gamma"}

    def test_strategy_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The issue's own shape: ``--strategy priority`` over a config's ``mark_all``."""
        config = self.config(tmp_path, conflicts={"strategy": "mark_all"})
        merged = self.run(runner, tmp_path, config, "--strategy", "priority")
        assert self.english(merged) == {"Beta"}

    def test_strategy_mark_all_config_still_marks(self, runner: CliRunner, tmp_path: Path) -> None:
        config = self.config(tmp_path, conflicts={"strategy": "mark_all"})
        merged = self.run(runner, tmp_path, config, exit_code=1)
        assert self.english(merged) == {"Alpha", "Beta", "Gamma"}

    # imports: one source imports ex:other.

    def imports_config(self, tmp_path: Path, **extra: Any) -> Path:
        source = tmp_path / "importer.ttl"
        source.write_text(
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            f"<http://example.org/o> a owl:Ontology ; owl:imports <{self.IMPORTED}> .\n",
            encoding="utf-8",
        )
        return write_yaml(tmp_path / "merge.yml", {"sources": [str(source)], **extra})

    def test_imports_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        merged = self.run(runner, tmp_path, self.imports_config(tmp_path, imports="remove"))
        assert not list(merged.objects(None, OWL.imports))

    def test_imports_flag_wins_when_given(self, runner: CliRunner, tmp_path: Path) -> None:
        merged = self.run(runner, tmp_path, self.imports_config(tmp_path), "--imports", "remove")
        assert not list(merged.objects(None, OWL.imports))

    def test_imports_flag_wins_when_given_at_its_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config = self.imports_config(tmp_path, imports="remove")
        merged = self.run(runner, tmp_path, config, "--imports", "preserve")
        assert list(merged.objects(None, OWL.imports)) == [self.IMPORTED]

    # -p: the config's priorities keep Beta; -p replaces them in order.

    def test_priority_config_wins_when_the_flag_is_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        assert self.english(self.run(runner, tmp_path, self.config(tmp_path))) == {"Beta"}

    def test_priority_flag_wins_when_given(self, runner: CliRunner, tmp_path: Path) -> None:
        merged = self.run(runner, tmp_path, self.config(tmp_path), "-p", "1", "-p", "1", "-p", "9")
        assert self.english(merged) == {"Gamma"}

    def test_a_short_priority_list_keeps_the_config_for_the_rest(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """``-p 9`` raises a above b's 3; b and c keep the config's 3 and 2."""
        merged = self.run(runner, tmp_path, self.config(tmp_path), "-p", "9")
        assert self.english(merged) == {"Alpha"}

    @pytest.mark.parametrize("with_config", [True, False], ids=["config", "sources"])
    def test_more_priorities_than_sources_is_refused(
        self, runner: CliRunner, tmp_path: Path, with_config: bool
    ) -> None:
        from tests.test_cli_smoke import assert_no_crash, assert_wrote_nothing, snapshot

        out = tmp_path / "merged.ttl"
        if with_config:
            argv = ["merge", "-c", str(self.config(tmp_path)), "-o", str(out)]
            argv += ["-p", "1", "-p", "2", "-p", "3", "-p", "4"]
            message = "-p gives 4 priorities for 3 source(s)"
        else:
            argv = ["merge", str(MERGE_LABELS / "labels_a.ttl"), str(MERGE_LABELS / "labels_b.ttl")]
            argv += ["-o", str(out), "-p", "1", "-p", "2", "-p", "3"]
            message = "-p gives 3 priorities for 2 source(s)"
        before = snapshot(argv, tmp_path)
        result = runner.invoke(cli, argv)
        assert_no_crash(result)
        assert result.exit_code == 2, result.output
        assert message in result.output
        assert_wrote_nothing(before, snapshot(argv, tmp_path))

    # --migrate-data and --data-output: the config migrates one file to one place.

    @staticmethod
    def data_file(path: Path, subject: str) -> Path:
        path.write_text(
            f"@prefix d: <http://example.org/d#> .\nd:{subject} a d:Record .\n", encoding="utf-8"
        )
        return path

    def migrating_config(self, tmp_path: Path) -> Path:
        data = self.data_file(tmp_path / "config_data.ttl", "fromConfig")
        return self.config(
            tmp_path,
            migrate_data={"sources": [str(data)], "output": str(tmp_path / "config_out.ttl")},
        )

    @staticmethod
    def subjects(path: Path) -> set[str]:
        return {str(s).rsplit("#", 1)[1] for s in Graph().parse(path).subjects()}

    def test_migrate_data_config_wins_when_the_flags_are_absent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        self.run(runner, tmp_path, self.migrating_config(tmp_path))
        assert self.subjects(tmp_path / "config_out.ttl") == {"fromConfig"}

    def test_migrate_data_flag_replaces_the_config_sources(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        given = self.data_file(tmp_path / "given.ttl", "fromFlag")
        self.run(runner, tmp_path, self.migrating_config(tmp_path), "--migrate-data", str(given))
        assert self.subjects(tmp_path / "config_out.ttl") == {"fromFlag"}

    def test_data_output_flag_replaces_the_config_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "flag_out.ttl"
        self.run(runner, tmp_path, self.migrating_config(tmp_path), "--data-output", str(out))
        assert self.subjects(out) == {"fromConfig"}
        assert not (tmp_path / "config_out.ttl").exists()

    def test_migrate_data_without_a_config_migration(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """#351's reproducer: a config with no ``migrate_data:`` and both flags given."""
        given = self.data_file(tmp_path / "given.ttl", "fromFlag")
        out = tmp_path / "flag_out.ttl"
        args = ("--migrate-data", str(given), "--data-output", str(out))
        self.run(runner, tmp_path, self.config(tmp_path), *args)
        assert self.subjects(out) == {"fromFlag"}
