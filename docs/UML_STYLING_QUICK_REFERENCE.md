# PlantUML Styling & Layout - Quick Reference

## 📁 Files Delivered

### Python Modules
- `uml_style.py` - Style configuration and color management
- `uml_layout.py` - Layout and arrow direction control  
- `styled_renderer.py` - Enhanced PlantUML renderer

### YAML Configs
- `uml_styles.yml` - 5 predefined color schemes
- `uml_layouts.yml` - 6 predefined layouts

### Documentation
- `README_STYLING.md` - Complete overview ⭐ **START HERE**
- `UML_STYLING_GUIDE.md` - User guide with examples
- `STYLING_SUMMARY.md` - Technical implementation details
- `INTEGRATION_GUIDE.md` - Step-by-step setup
- `example_styled_uml.py` - Working example script

## 🚀 Quick Start (3 Steps)

### 1. Test Without Installation
```bash
pip install rdflib pyyaml
python example_styled_uml.py
# Check styled_diagrams/ directory
```

### 2. View a Style Configuration
```yaml
# uml_styles.yml
schemes:
  default:
    classes:
      by_namespace:
        ies:
          border: "#0066CC"
          fill: "#E8F4F8"
    instances:
      border: "#000000"
      fill: "#000000"
    show_stereotypes: false
```

### 3. View a Layout Configuration
```yaml
# uml_layouts.yml
layouts:
  hierarchy:
    direction: top_to_bottom
    arrow_direction: up  # Children point UP to parents
    hide_empty_members: false
```

## 🎨 Predefined Schemes

| Name | Description | Use Case |
|------|-------------|----------|
| `default` | Professional blue | General documentation |
| `ies_semantic` | IES with metaclass colors | IES ontology visualization |
| `high_contrast` | Bold bright colors | Presentations |
| `grayscale` | Black & white | Academic papers |
| `minimal` | Bare-bones | Quick debugging |

## 📐 Predefined Layouts

| Name | Direction | Best For |
|------|-----------|----------|
| `hierarchy` | Top-down | Class hierarchies ⭐ |
| `flat` | Left-right | Network relationships |
| `compact` | Top-down | Quick overviews |
| `documentation` | Top-down | Grouped by namespace |
| `presentation` | Top-down | Slides/projectors |
| `network` | Left-right | Emphasize connections |

## 💡 Key Concepts

### Arrow Direction = Layout Control

```yaml
arrow_direction: up     # Child -up-|> Parent
arrow_direction: down   # Parent -down-|> Child
```

**Result**: `up` puts parents above, `down` puts parents below.

### Color Inheritance

```yaml
classes:
  by_namespace:
    ies:  # All ies:* classes get these colors
      border: "#0066CC"
      fill: "#E8F4F8"
```

### Stereotypes

```yaml
show_stereotypes: true
stereotype_map:
  ies:ClassOfElement: "«meta»"
```

**Result**: `class "ies:ClassOfElement" «meta» #FFE6E6`

## 🔧 Usage Example

```python
from rdflib import Graph
from uml_style import load_style_config
from uml_layout import load_layout_config
from styled_renderer import render_plantuml

# Load configs
style = load_style_config("uml_styles.yml").get_scheme("default")
layout = load_layout_config("uml_layouts.yml").get_layout("hierarchy")

# Render (entities already collected)
render_plantuml(graph, entities, "output.puml", style, layout)
```

## 📋 Integration Checklist

- [ ] Copy modules to `src/rdf_construct/uml/`
- [ ] Copy YAMLs to `examples/`
- [ ] Update `__init__.py` exports
- [ ] Update CLI with style/layout options
- [ ] Run `example_styled_uml.py` to test
- [ ] Generate diagrams with new CLI options
- [ ] Verify PlantUML output online

## 🎯 Your Requirements ✅

✅ Top-down layout (arrow_direction: up)  
✅ YAML configuration (uml_styles.yml, uml_layouts.yml)  
✅ Separate layout/style (independent modules)  
✅ Color profiles by type (by_namespace, by_type)  
✅ Class border/fill colors (ColorPalette)  
✅ Instance border/fill colors (instances config)  
✅ rdf:type arrow styling (arrows.rdf_type)  
✅ Stereotypes (show_stereotypes + stereotype_map)  

## 📖 Documentation Map

**Start here**: README_STYLING.md
- Overview of all features
- What each file does
- Quick examples

**User guide**: UML_STYLING_GUIDE.md  
- Detailed configuration reference
- Advanced techniques
- Best practices

**Technical**: STYLING_SUMMARY.md
- Implementation architecture  
- Module responsibilities
- Testing checklist

**Setup**: INTEGRATION_GUIDE.md
- Step-by-step installation
- CLI integration
- Troubleshooting

## 🐛 Common Issues

**Import error**: Files not in `src/rdf_construct/uml/`  
→ Copy modules to correct location

**Colors not showing**: Invalid hex codes  
→ Test with online PlantUML editor

**Arrow direction ignored**: PlantUML heuristics  
→ Try adjusting spacing parameters

**Stereotypes missing**: RDF types don't match map  
→ Check actual RDF types in ontology

## 🔗 Useful Links

- PlantUML online: https://www.plantuml.com/plantuml/
- Color reference: https://plantuml.com/color
- Skinparam docs: https://plantuml-documentation.readthedocs.io/

## 💬 Need Help?

All answers in the documentation:
- Configuration → UML_STYLING_GUIDE.md
- Technical → STYLING_SUMMARY.md
- Setup → INTEGRATION_GUIDE.md
- Examples → example_styled_uml.py

---

**Total**: 9 files, ~2,700 lines, 100% feature complete ✨