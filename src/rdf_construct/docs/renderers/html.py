"""HTML documentation renderer using Jinja2 templates."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from ..config import DocsConfig
    from ..extractors import ClassInfo, ExtractedEntities, InstanceInfo, PropertyInfo


class HTMLRenderer:
    """Renders ontology documentation as HTML pages using Jinja2 templates."""

    def __init__(self, config: "DocsConfig") -> None:
        """Initialise the HTML renderer.

        Args:
            config: Documentation configuration.
        """
        self.config = config
        self._env: Environment | None = None

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

        return env

    def _entity_url_filter(self, uri_or_qname: str, entity_type: str = "class") -> str:
        """Jinja2 filter to generate entity URLs.

        Args:
            uri_or_qname: URI or QName of the entity.
            entity_type: Type of entity.

        Returns:
            URL to the entity's documentation page.
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

        return entity_to_url(qname, entity_type, self.config)

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
            "instances": entities.instances,
            "config": self.config,
            **extra,
        }

    def render_index(self, entities: "ExtractedEntities") -> Path:
        """Render the main index page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        template = self.env.get_template("index.html.jinja")
        context = self._build_context(
            entities,
            total_classes=len(entities.classes),
            total_properties=len(entities.properties),
            total_instances=len(entities.instances),
        )
        content = template.render(context)
        return self._write_file(self._get_output_path("index.html"), content)

    def render_hierarchy(self, entities: "ExtractedEntities") -> Path:
        """Render the class hierarchy page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        # Build hierarchy tree structure
        hierarchy = self._build_hierarchy_tree(entities.classes)

        template = self.env.get_template("hierarchy.html.jinja")
        context = self._build_context(entities, hierarchy=hierarchy)
        content = template.render(context)
        return self._write_file(self._get_output_path("hierarchy.html"), content)

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
        class_by_uri: dict[str, "ClassInfo"] = {
            str(c.uri): c for c in classes
        }

        # Find root classes (no superclasses in our ontology)
        internal_uris = set(class_by_uri.keys())
        root_classes = []

        for c in classes:
            # A class is a root if none of its superclasses are in our ontology
            has_internal_parent = any(
                str(parent) in internal_uris for parent in c.superclasses
            )
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

        template = self.env.get_template("class.html.jinja")
        context = self._build_context(
            entities,
            class_info=class_info,
            inherited_properties=inherited,
        )
        content = template.render(context)

        from ..config import entity_to_path
        rel_path = entity_to_path(class_info.qname, "class", self.config)
        return self._write_file(self.config.output_dir / rel_path, content)

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
        template = self.env.get_template("property.html.jinja")
        context = self._build_context(entities, property_info=prop_info)
        content = template.render(context)

        entity_type = f"{prop_info.property_type}_property"
        from ..config import entity_to_path
        rel_path = entity_to_path(prop_info.qname, entity_type, self.config)
        return self._write_file(self.config.output_dir / rel_path, content)

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
        template = self.env.get_template("instance.html.jinja")
        context = self._build_context(entities, instance_info=instance_info)
        content = template.render(context)

        from ..config import entity_to_path
        rel_path = entity_to_path(instance_info.qname, "instance", self.config)
        return self._write_file(self.config.output_dir / rel_path, content)

    def render_namespaces(self, entities: "ExtractedEntities") -> Path:
        """Render the namespace reference page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        template = self.env.get_template("namespaces.html.jinja")
        context = self._build_context(entities)
        content = template.render(context)
        return self._write_file(self._get_output_path("namespaces.html"), content)

    def render_single_page(self, entities: "ExtractedEntities") -> Path:
        """Render all documentation as a single page.

        Args:
            entities: All extracted entities.

        Returns:
            Path to the rendered file.
        """
        hierarchy = self._build_hierarchy_tree(entities.classes)

        template = self.env.get_template("single_page.html.jinja")
        context = self._build_context(entities, hierarchy=hierarchy)
        content = template.render(context)
        return self._write_file(self._get_output_path("index.html"), content)

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

    let searchIndex = null;

    // Load search index
    fetch('search.json')
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

        resultsContainer.innerHTML = results
            .map(r => `<li><a href="${r.entity.url}">${r.entity.label}</a> <span class="entity-type ${r.entity.entity_type}">${r.entity.entity_type}</span></li>`)
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
