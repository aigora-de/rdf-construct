"""HTML documentation renderer using Jinja2 templates."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from rdflib import URIRef

    from ..config import DocsConfig
    from ..extractors import (
        ClassInfo,
        ConceptInfo,
        ConceptSchemeInfo,
        ExtractedEntities,
        InstanceInfo,
        PropertyInfo,
        ShapeInfo,
    )


class HTMLRenderer:
    """Renders ontology documentation as HTML pages using Jinja2 templates."""

    def __init__(self, config: "DocsConfig") -> None:
        """Initialise the HTML renderer.

        Args:
            config: Documentation configuration.
        """
        self.config = config
        self._env: Environment | None = None
        # Path of the page currently being rendered, relative to the docs
        # output directory. Used by `_entity_url_filter` to produce URLs
        # that resolve correctly from the page's own location when no
        # absolute `config.base_url` is set. See issue #59.
        self._current_page: Path | None = None
        # Cached URI -> link-pieces index; see `_reference_index`. Keyed by
        # the identity of the entity set it was built from so a second
        # generate() on the same renderer cannot serve a stale index.
        self._ref_index: dict[str, dict[str, Any]] | None = None
        self._ref_index_for: "ExtractedEntities | None" = None

    @property
    def env(self) -> Environment:
        """Get the Jinja2 environment.

        Returns:
            Configured Jinja2 Environment.
        """
        if self._env is None:
            self._env = self._create_environment()
        return self._env

    def _create_environment(self) -> Environment:
        """Create and configure the Jinja2 environment.

        Returns:
            Configured Environment.
        """
        # Use custom template directory if provided, otherwise package templates
        if self.config.template_dir and self.config.template_dir.exists():
            loader = FileSystemLoader(str(self.config.template_dir / "html"))
        else:
            # Use package templates
            loader = PackageLoader("rdf_construct.docs", "templates/html")

        env = Environment(
            loader=loader,
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        env.filters["entity_url"] = self._entity_url_filter
        env.filters["qname_local"] = self._qname_local_filter

        # Add global context
        env.globals["config"] = self.config
        # Templates ask this before emitting a cross-reference: a link to a
        # page this run is not generating is a dead link (#115).
        env.globals["included"] = self._included

        return env

    def _entity_url_filter(self, uri_or_qname: str, entity_type: str = "class") -> str:
        """Jinja2 filter to generate entity URLs.

        Args:
            uri_or_qname: URI or QName of the entity.
            entity_type: Type of entity.

        Returns:
            URL to the entity's documentation page, made relative to the
            page currently being rendered when no ``config.base_url`` is set.
        """
        from ..config import entity_to_url

        # If it looks like a full URI, try to extract local name
        if uri_or_qname.startswith("http"):
            if "#" in uri_or_qname:
                qname = uri_or_qname.split("#")[-1]
            elif "/" in uri_or_qname:
                qname = uri_or_qname.split("/")[-1]
            else:
                qname = uri_or_qname
        else:
            qname = uri_or_qname

        return entity_to_url(qname, entity_type, self.config, from_path=self._current_page)

    def _included(self, entity_type: str) -> bool:
        """Whether this run generates pages of the given entity type.

        Exposed to templates as ``included(...)``. See
        :func:`rdf_construct.docs.config.entity_type_included`.
        """
        from ..config import entity_type_included

        return entity_type_included(entity_type, self.config)

    def _qname_local_filter(self, qname: str) -> str:
        """Jinja2 filter to get the local part of a QName.

        Args:
            qname: Qualified name like 'ex:Building'.

        Returns:
            Local name like 'Building'.
        """
        if ":" in qname:
            return qname.split(":", 1)[1]
        return qname

    def _get_output_path(self, filename: str, subdir: str | None = None) -> Path:
        """Get the full output path for a file.

        Args:
            filename: Name of the file.
            subdir: Optional subdirectory.

        Returns:
            Full output path.
        """
        if subdir:
            path = self.config.output_dir / subdir / filename
        else:
            path = self.config.output_dir / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_file(self, path: Path, content: str) -> Path:
        """Write content to a file.

        Args:
            path: Output path.
            content: Content to write.

        Returns:
            Path to the written file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _build_context(
        self,
        entities: "ExtractedEntities",
        **extra: Any,
    ) -> dict[str, Any]:
        """Build the template context.

        Args:
            entities: All extracted entities.
            **extra: Additional context variables.

        Returns:
            Template context dictionary.
        """
        return {
            "ontology": entities.ontology,
            "classes": entities.classes,
            "object_properties": entities.object_properties,
            "datatype_properties": entities.datatype_properties,
            "annotation_properties": entities.annotation_properties,
            "other_properties": entities.other_properties,
            "instances": entities.instances,
            "shapes": entities.shapes,
            "node_shapes": entities.node_shapes,
            "property_shapes": entities.property_shapes,
            "concepts": entities.concepts,
            "concept_schemes": entities.concept_schemes,
            "config": self.config,
            **extra,
        }

    def _reference_index(
        self,
        entities: "ExtractedEntities",
    ) -> dict[str, dict[str, Any]]:
        """Build (once) a URI -> link-pieces index for cross-referencing.

        Built once per set of extracted entities and cached on the
        renderer, rather than scanning every bucket for every reference:
        a vocabulary with a few thousand concepts renders several
        references per page, and the linear form is quadratic in the size
        of the ontology.

        Later buckets do not overwrite earlier ones, which is what
        encodes the routing order — a subject documented as a class links
        to its class page even when it is also a concept.

        Args:
            entities: All extracted entities.

        Returns:
            Mapping of URI string to ``label`` / ``qname`` /
            ``entity_type`` dicts.
        """
        if self._ref_index is not None and self._ref_index_for is entities:
            return self._ref_index

        index: dict[str, dict[str, Any]] = {}

        def add(uri: Any, label: str | None, qname: str, entity_type: str) -> None:
            key = str(uri)
            if key not in index:
                index[key] = {"label": label or qname, "qname": qname, "entity_type": entity_type}

        for class_info in entities.classes:
            add(class_info.uri, class_info.label, class_info.qname, "class")
        for prop in entities.properties:
            add(prop.uri, prop.label, prop.qname, f"{prop.property_type}_property")
        for shape in entities.shapes:
            add(shape.uri, shape.label, shape.qname, "shape")
        for scheme in entities.concept_schemes:
            add(scheme.uri, scheme.label, scheme.qname, "skos_concept_scheme")
        for concept in entities.concepts:
            add(concept.uri, concept.label, concept.qname, "skos_concept")
        for instance in entities.instances:
            add(instance.uri, instance.label, instance.qname, "instance")

        self._ref_index = index
        self._ref_index_for = entities
        return index

    def _entity_reference(
        self,
        uri: "URIRef | str",
        entities: "ExtractedEntities",
    ) -> dict[str, Any]:
        """Resolve a URI to the pieces a template needs to link to it.

        Returns ``qname`` and ``entity_type`` rather than a finished URL:
        the ``entity_url`` filter has to run during template rendering, when
        the renderer knows which page the link is being written on. A URI
        that belongs to no documented entity comes back with
        ``entity_type=None`` so the template can fall back to plain text
        rather than emitting a link to a page that was never generated.

        Args:
            uri: URI to resolve.
            entities: All extracted entities.

        Returns:
            Dict with ``label``, ``qname`` and ``entity_type`` keys.
        """
        uri_str = str(uri)
        resolved = self._reference_index(entities).get(uri_str)
        if resolved is not None:
            # An entity whose type this run excludes has no page to link to,
            # so it degrades to plain text exactly as an undocumented one
            # does (#115) — the reference stays visible either way.
            if not self._included(str(resolved["entity_type"])):
                return {**resolved, "entity_type": None}
            return resolved
        return {"label": uri_str, "qname": uri_str, "entity_type": None}

    def _entity_references(
        self,
        uris: "list[URIRef]",
        entities: "ExtractedEntities",
    ) -> list[dict[str, Any]]:
        """Resolve a list of URIs. See :meth:`_entity_reference`."""
        return [self._entity_reference(uri, entities) for uri in uris]

    def _render_page(
        self,
        template_name: str,
        rel_path: Path,
        context: dict[str, Any],
    ) -> Path:
        """Render a template to its output file with correct path handling.

        Sets the renderer's notion of the "current page" for the duration
        of the render so that the ``entity_url`` filter and the
        ``relative_root`` template variable resolve to URLs that are
        correct from this page's location. See issue #59.

        Args:
            template_name: Name of the Jinja2 template to render.
            rel_path: Path of the output file, relative to the docs output
                directory.
            context: Template context (will be augmented with
                ``relative_root``).

        Returns:
            Path of the written output file.
        """
        from ..config import relative_url_prefix

        previous_page = self._current_page
        self._current_page = rel_path
        try:
            template = self.env.get_template(template_name)
            context["relative_root"] = relative_url_prefix(rel_path)
            content = template.render(context)
            return self._write_file(self.config.output_dir / rel_path, content)
        finally:
            self._current_page = previous_page

    def render_index(self, entities: "ExtractedEntities") -> Path:
        """Render the main index page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(
            entities,
            total_classes=len(entities.classes),
            total_properties=len(entities.properties),
            total_instances=len(entities.instances),
        )
        return self._render_page("index.html.jinja", Path("index.html"), context)

    def render_hierarchy(self, entities: "ExtractedEntities") -> Path:
        """Render the class hierarchy page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        # Build hierarchy tree structure
        hierarchy = self._build_hierarchy_tree(entities.classes)

        context = self._build_context(entities, hierarchy=hierarchy)
        return self._render_page("hierarchy.html.jinja", Path("hierarchy.html"), context)

    def _build_hierarchy_tree(
        self,
        classes: list["ClassInfo"],
    ) -> list[dict[str, Any]]:
        """Build a tree structure for the class hierarchy.

        Args:
            classes: List of all classes.

        Returns:
            Nested list structure representing the hierarchy.
        """
        # Index classes by URI for lookup
        class_by_uri: dict[str, "ClassInfo"] = {str(c.uri): c for c in classes}

        # Find root classes (no superclasses in our ontology)
        internal_uris = set(class_by_uri.keys())
        root_classes = []

        for c in classes:
            # A class is a root if none of its superclasses are in our ontology
            has_internal_parent = any(str(parent) in internal_uris for parent in c.superclasses)
            if not has_internal_parent:
                root_classes.append(c)

        def build_node(class_info: "ClassInfo") -> dict[str, Any]:
            """Recursively build a tree node."""
            children = []
            for child_uri in class_info.subclasses:
                child_key = str(child_uri)
                if child_key in class_by_uri:
                    children.append(build_node(class_by_uri[child_key]))

            return {
                "class": class_info,
                "children": sorted(children, key=lambda n: n["class"].qname),
            }

        return sorted(
            [build_node(c) for c in root_classes],
            key=lambda n: n["class"].qname,
        )

    def render_class(
        self,
        class_info: "ClassInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a class documentation page.

        Args:
            class_info: Class to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        # Find inherited properties (from superclasses)
        inherited = self._collect_inherited_properties(class_info, entities)

        context = self._build_context(
            entities,
            class_info=class_info,
            inherited_properties=inherited,
        )

        from ..config import entity_to_path

        rel_path = entity_to_path(class_info.qname, "class", self.config)
        return self._render_page("class.html.jinja", rel_path, context)

    def _collect_inherited_properties(
        self,
        class_info: "ClassInfo",
        entities: "ExtractedEntities",
    ) -> list["PropertyInfo"]:
        """Collect properties inherited from superclasses.

        Args:
            class_info: Class to collect for.
            entities: All entities for lookups.

        Returns:
            List of inherited properties.
        """
        # Index classes by URI
        class_by_uri = {str(c.uri): c for c in entities.classes}

        inherited: list["PropertyInfo"] = []
        seen_props: set[str] = set()
        visited_classes: set[str] = set()

        # Direct properties
        for prop in class_info.domain_of:
            seen_props.add(str(prop.uri))

        def collect_from_ancestors(uri: str) -> None:
            """Recursively collect from ancestor classes."""
            if uri not in class_by_uri:
                return
            if uri in visited_classes:
                return  # Avoid circular hierarchies
            visited_classes.add(uri)

            ancestor = class_by_uri[uri]
            for prop in ancestor.domain_of:
                if str(prop.uri) not in seen_props:
                    seen_props.add(str(prop.uri))
                    inherited.append(prop)

            for parent_uri in ancestor.superclasses:
                collect_from_ancestors(str(parent_uri))

        for parent_uri in class_info.superclasses:
            collect_from_ancestors(str(parent_uri))

        return inherited

    def render_property(
        self,
        prop_info: "PropertyInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a property documentation page.

        Args:
            prop_info: Property to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(entities, property_info=prop_info)

        entity_type = f"{prop_info.property_type}_property"
        from ..config import entity_to_path

        rel_path = entity_to_path(prop_info.qname, entity_type, self.config)
        return self._render_page("property.html.jinja", rel_path, context)

    def render_instance(
        self,
        instance_info: "InstanceInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render an instance documentation page.

        Args:
            instance_info: Instance to render.
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(entities, instance_info=instance_info)

        from ..config import entity_to_path

        rel_path = entity_to_path(instance_info.qname, "instance", self.config)
        return self._render_page("instance.html.jinja", rel_path, context)

    def render_shape(
        self,
        shape_info: "ShapeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SHACL shape documentation page.

        Renders both NodeShapes and named PropertyShapes from the same
        template; the kind badges on the page distinguish them. Inline
        PropertyShape arcs (blank-node ``sh:property`` children of a
        NodeShape) are rendered as a constraint table within the parent
        NodeShape's page — they do not get their own pages.

        Args:
            shape_info: Shape to render.
            entities: All extracted entities (for cross-references).

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(entities, shape_info=shape_info)

        from ..config import entity_to_path

        rel_path = entity_to_path(shape_info.qname, "shape", self.config)
        return self._render_page("shape.html.jinja", rel_path, context)

    def render_concept(
        self,
        concept_info: "ConceptInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept documentation page.

        Broader, narrower, related and scheme references are resolved to
        cross-links here rather than in the template, so a reference to a
        concept that was never documented degrades to plain text instead of
        a dead link.

        Args:
            concept_info: Concept to render.
            entities: All extracted entities (for cross-references).

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(
            entities,
            concept_info=concept_info,
            broader_refs=self._entity_references(concept_info.broader, entities),
            narrower_refs=self._entity_references(concept_info.narrower, entities),
            related_refs=self._entity_references(concept_info.related, entities),
            scheme_refs=self._entity_references(concept_info.in_schemes, entities),
            top_concept_of_refs=self._entity_references(concept_info.top_concept_of, entities),
            type_refs=self._entity_references(concept_info.types, entities),
        )

        from ..config import entity_to_path

        rel_path = entity_to_path(concept_info.qname, "skos_concept", self.config)
        return self._render_page("concept.html.jinja", rel_path, context)

    def render_concept_scheme(
        self,
        scheme_info: "ConceptSchemeInfo",
        entities: "ExtractedEntities",
    ) -> Path:
        """Render a SKOS concept scheme documentation page.

        Carries the scheme's broader/narrower tree — the natural way to
        navigate a vocabulary — alongside a flat member list. The tree
        walker is cycle-safe; see
        :func:`rdf_construct.docs.extractors.build_concept_tree`.

        Args:
            scheme_info: Concept scheme to render.
            entities: All extracted entities (for cross-references).

        Returns:
            Path to the rendered file.
        """
        from ..extractors import build_concept_tree

        tree = build_concept_tree(entities.concepts, scheme_info.uri)

        context = self._build_context(
            entities,
            scheme_info=scheme_info,
            concept_tree=tree,
            top_concept_refs=self._entity_references(scheme_info.top_concepts, entities),
            member_refs=self._entity_references(scheme_info.concepts, entities),
        )

        from ..config import entity_to_path

        rel_path = entity_to_path(scheme_info.qname, "skos_concept_scheme", self.config)
        return self._render_page("concept_scheme.html.jinja", rel_path, context)

    def render_namespaces(self, entities: "ExtractedEntities") -> Path:
        """Render the namespace reference page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        context = self._build_context(entities)
        return self._render_page("namespaces.html.jinja", Path("namespaces.html"), context)

    def render_single_page(self, entities: "ExtractedEntities") -> Path:
        """Render all documentation as a single page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        hierarchy = self._build_hierarchy_tree(entities.classes)

        context = self._build_context(entities, hierarchy=hierarchy)
        return self._render_page("single_page.html.jinja", Path("index.html"), context)

    def copy_assets(self) -> None:
        """Copy static assets (CSS, JS) to the output directory."""
        assets_dir = self.config.output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # If using custom templates with custom assets, copy those
        if self.config.template_dir:
            custom_assets = self.config.template_dir / "assets"
            if custom_assets.exists():
                for asset in custom_assets.iterdir():
                    if asset.is_file():
                        shutil.copy(asset, assets_dir / asset.name)
                return

        # Write default CSS
        self._write_default_css(assets_dir)

        # Write default search JS
        if self.config.include_search:
            self._write_default_search_js(assets_dir)

    def _write_default_css(self, assets_dir: Path) -> None:
        """Write the default stylesheet.

        Args:
            assets_dir: Assets directory.
        """
        css = """/* rdf-construct documentation styles */
:root {
    --primary-colour: #2563eb;
    --secondary-colour: #64748b;
    --background: #ffffff;
    --surface: #f8fafc;
    --text: #1e293b;
    --text-muted: #64748b;
    --border: #e2e8f0;
    --code-bg: #f1f5f9;
    --success: #22c55e;
    --warning: #eab308;
    --error: #ef4444;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background: var(--background);
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

a {
    color: var(--primary-colour);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

h1, h2, h3, h4 {
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
    line-height: 1.3;
}

h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.25rem; }
h4 { font-size: 1.1rem; }

.header {
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 2rem;
}

.header h1 {
    margin-top: 0;
}

.header .description {
    color: var(--text-muted);
    font-size: 1.1rem;
}

.nav {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border);
}

.nav a {
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    transition: background 0.2s;
}

.nav a:hover {
    background: var(--surface);
    text-decoration: none;
}

.nav a.active {
    background: var(--primary-colour);
    color: white;
}

.search-box {
    margin-bottom: 1.5rem;
}

.search-box input {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border);
    border-radius: 0.375rem;
    font-size: 1rem;
}

.search-box input:focus {
    outline: none;
    border-colour: var(--primary-colour);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.search-results {
    list-style: none;
    padding: 0;
    margin-top: 1rem;
}

.search-results li {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
}

.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin: 1.5rem 0;
}

.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 1rem;
    text-align: center;
}

.stat-card .number {
    font-size: 2rem;
    font-weight: 600;
    color: var(--primary-colour);
}

.stat-card .label {
    color: var(--text-muted);
    font-size: 0.875rem;
}

.entity-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

.entity-card h2 {
    margin-top: 0;
}

.entity-type {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    background: var(--primary-colour);
    color: white;
    margin-left: 0.5rem;
}

.entity-type.object { background: #8b5cf6; }
.entity-type.datatype { background: #06b6d4; }
.entity-type.annotation { background: #f59e0b; }
.entity-type.instance { background: #10b981; }

/* Properties whose kind is not implied by their declaration (#76) —
   rdf:Property, owl:FunctionalProperty, owl:DeprecatedProperty. Neutral
   slate rather than a hue: the badge's job is to say "the source does not
   state which kind this is", and a saturated colour would imply it sits
   alongside object/datatype/annotation as a fourth kind. 10.35:1 against
   white, clearing WCAG AA, and outside every hue family in the palette
   (nearest neighbour 5.8 CIEDE2000, under simulated tritanopia). */
.entity-type.rdf { background: #334155; }

/* Shape badges (#60). Red-to-rose hue family signals kinship between
   NodeShape and PropertyShape; brightness gradient (NodeShape darker
   than PropertyShape) reads as parent-child. All three pass WCAG AA
   contrast against the badge's white text:
     .shape          #dc2626  4.83:1
     .node_shape     #b91c1c  6.47:1
     .property_shape #e11d48  4.70:1
   The hue family is distinct from the other four badges under common
   colour-vision deficiencies (amber goes pale-yellow under
   deuteranopia; reds stay warm-saturated). Badge text labels
   ("node shape" / "property shape") carry the category regardless of
   perceived colour. */
.entity-type.shape { background: #dc2626; }
.entity-type.node_shape { background: #b91c1c; }
.entity-type.property_shape { background: #e11d48; }

/* SKOS badges (#63). Blue family, with the scheme darker than the concept
   so the container reads as the parent — the same gradient the shape
   family uses. Contrast against the badge's white text:
     .skos_concept        #1d4ed8   6.70:1
     .skos_concept_scheme #1e3a8a  10.36:1
   Both clear WCAG AA for normal text. Blue was measured against the
   existing badges rather than assumed: the indigo family suggested in
   #63 sits only 11.3 CIEDE2000 units from the object-property violet
   (10.7 under simulated deuteranopia), which is too close to call apart,
   whereas #1d4ed8 keeps 15.3 (17.7 deuteranopia, 21.3 protanopia). Its
   one weak axis is tritanopia, where it falls to 6.0 against the instance
   emerald — still distinguishable, and the badge's text label carries the
   category regardless. */
.entity-type.skos_concept { background: #1d4ed8; }
.entity-type.skos_concept_scheme { background: #1e3a8a; }

/* Named-individual badge (#64). A darker, deeper emerald than the plain
   instance badge it sits beside, so the two read as one family the way
   NodeShape and PropertyShape share red-rose:
     .instance         #10b981  (existing)
     .named_individual #047857  5.48:1 — clears WCAG AA against white
   It stays 21.7 CIEDE2000 units from the instance emerald in normal
   vision and 15.3 under simulated deuteranopia — related, not confusable
   — and is further still from every other badge in the palette. */
.entity-type.named_individual { background: #047857; }

/* Language tag beside a SKOS label or note value. */
.lang-tag {
    font-family: 'SF Mono', Consolas, monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 0.25rem;
    padding: 0 0.25rem;
    margin-left: 0.25rem;
}

/* Concept hierarchy tree on a scheme page — reuses the class-hierarchy
   connectors so a vocabulary tree looks like the class tree. */
.concept-tree {
    list-style: none;
    padding-left: 1.5rem;
}

.concept-tree li {
    position: relative;
    padding: 0.25rem 0;
}

/* PropertyShape constraint table on shape pages. Tighter than the
   default annotations table — the `th` is the constraint name, the
   `td` is the value. */
.property-shape-constraints {
    margin: 0.5rem 0 1rem 0;
}
.property-shape-constraints th {
    width: 10rem;
    font-weight: 600;
    text-align: left;
    background: var(--surface);
    padding: 0.5rem 0.75rem;
}
.property-shape-constraints td {
    padding: 0.5rem 0.75rem;
}

.property-shape {
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 0.375rem;
    padding: 0.75rem 1rem;
    margin-bottom: 0.75rem;
}
.property-shape h4 {
    margin-top: 0;
    margin-bottom: 0.5rem;
    font-size: 1rem;
}

.definition {
    color: var(--text-muted);
    font-style: italic;
    margin-bottom: 1rem;
}

.uri {
    font-family: monospace;
    font-size: 0.875rem;
    color: var(--text-muted);
    word-break: break-all;
}

.section {
    margin: 1.5rem 0;
}

.section h3 {
    font-size: 1rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
}

.entity-list {
    list-style: none;
    padding: 0;
}

.entity-list li {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
}

.entity-list li:last-child {
    border-bottom: none;
}

.hierarchy-tree {
    list-style: none;
    padding-left: 1.5rem;
}

.hierarchy-tree > li {
    padding-left: 0;
}

.hierarchy-tree li {
    position: relative;
    padding: 0.25rem 0;
}

.hierarchy-tree li::before {
    content: '';
    position: absolute;
    left: -1rem;
    top: 0;
    border-left: 1px solid var(--border);
    height: 100%;
}

.hierarchy-tree li::after {
    content: '';
    position: absolute;
    left: -1rem;
    top: 0.75rem;
    border-bottom: 1px solid var(--border);
    width: 0.75rem;
}

.hierarchy-tree li:last-child::before {
    height: 0.75rem;
}

.annotation {
    background: var(--code-bg);
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-size: 0.875rem;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
}

th, td {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

th {
    background: var(--surface);
    font-weight: 600;
}

code {
    font-family: 'SF Mono', Consolas, monospace;
    font-size: 0.875em;
    background: var(--code-bg);
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
}

.footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.875rem;
    text-align: center;
}

@media (max-width: 768px) {
    body {
        padding: 1rem;
    }

    .stats {
        grid-template-columns: repeat(2, 1fr);
    }

    .nav {
        flex-wrap: wrap;
    }
}
"""
        (assets_dir / "style.css").write_text(css, encoding="utf-8")

    def _write_default_search_js(self, assets_dir: Path) -> None:
        """Write the default search JavaScript.

        Args:
            assets_dir: Assets directory.
        """
        js = """// rdf-construct documentation search
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const resultsContainer = document.getElementById('search-results');

    if (!searchInput || !resultsContainer) return;

    // Where the docs root sits relative to THIS page. Set by base.html.jinja,
    // which computes it per page (".", "..", "../.." or an absolute base_url).
    // Falling back to "." keeps a hand-written page working at the root.
    const docsRoot = (typeof window.DOCS_ROOT === 'string' && window.DOCS_ROOT)
        ? window.DOCS_ROOT.replace(/\\/$/, '')
        : '.';

    // fetch() is blocked by CORS on file:// regardless of the path, so search
    // cannot work from a double-clicked page. Say so rather than presenting a
    // box that silently does nothing.
    if (window.location.protocol === 'file:') {
        searchInput.disabled = true;
        searchInput.placeholder = 'Search needs an HTTP server (unavailable when opened as a file)';
        return;
    }

    let searchIndex = null;

    // Load search index, resolved from this page rather than assuming the root
    fetch(docsRoot + '/search.json')
        .then(response => response.json())
        .then(data => {
            searchIndex = data.entities;
        })
        .catch(err => console.error('Failed to load search index:', err));

    // Search function
    function search(query) {
        if (!searchIndex || query.length < 2) {
            resultsContainer.innerHTML = '';
            return;
        }

        const terms = query.toLowerCase().split(/\\s+/);
        const results = searchIndex
            .map(entity => {
                const score = terms.reduce((acc, term) => {
                    // Check label
                    if (entity.label.toLowerCase().includes(term)) {
                        return acc + 10;
                    }
                    // Check qname
                    if (entity.qname.toLowerCase().includes(term)) {
                        return acc + 5;
                    }
                    // Check keywords
                    if (entity.keywords.some(k => k.includes(term))) {
                        return acc + 1;
                    }
                    return acc;
                }, 0);
                return { entity, score };
            })
            .filter(r => r.score > 0)
            .sort((a, b) => b.score - a.score)
            .slice(0, 20);

        if (results.length === 0) {
            resultsContainer.innerHTML = '<li>No results found</li>';
            return;
        }

        // Entry URLs in search.json are stored relative to the docs root, so
        // they have to be resolved against it — injected verbatim they
        // resolve against the current page and 404 from any sub-folder.
        resultsContainer.innerHTML = results
            .map(r => `<li><a href="${docsRoot}/${r.entity.url}">${r.entity.label}</a> <span class="entity-type ${r.entity.entity_type}">${r.entity.entity_type}</span></li>`)
            .join('');
    }

    // Debounce search
    let timeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(timeout);
        timeout = setTimeout(() => search(this.value), 150);
    });
});
"""
        (assets_dir / "search.js").write_text(js, encoding="utf-8")
