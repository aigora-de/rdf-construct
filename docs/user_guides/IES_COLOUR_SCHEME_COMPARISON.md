# IES Colour Palette - Scheme Comparison

## Overview

The IES colour palette includes three schemes optimized for different use cases. This document compares them side-by-side to help you choose the right scheme for your needs.

## Quick Comparison

| Feature | ies_full | ies_core | ies_metaclass |
|---------|----------|----------|---------------|
| **Explicit Classes** | 18 classes | 5 classes | 14 classes |
| **Metaclass Emphasis** | Balanced | Low | High |
| **Border Inheritance** | Yes | No | Yes |
| **Stereotypes** | Optional | No | Yes |
| **Complexity** | High | Low | Medium |
| **Best For** | Documentation | Design sessions | Teaching |

## Detailed Comparison

### Core Hierarchy Classes

| Class | ies_full | ies_core | ies_metaclass |
|-------|----------|----------|---------------|
| **ies:Thing** | Explicit: #FFFFFF | Namespace: cyan | Namespace: grey |
| **ies:Element** | Explicit: #FFFFFF | Namespace: cyan | Explicit: grey |
| **ies:Entity** | Explicit: #FEFE54 (yellow) | Explicit: #FEFE54 (yellow) | Explicit: #FFFFCC (pale) |
| **ies:State** | Explicit: #F7D748 (golden) | Explicit: #F7D748 (golden) | Explicit: #FFFFDD (pale) |
| **ies:Event** | Explicit: #F5C2CB (pink) | Explicit: #F5C2CB (pink) | Explicit: #FFE6E6 (pale) |
| **ies:PeriodOfTime** | Explicit: #F3B169 (orange) | Explicit: #F3B169 (orange) | Namespace: grey |

### Metaclass Hierarchy (First Order)

| Class | ies_full | ies_core | ies_metaclass |
|-------|----------|----------|---------------|
| **ies:ClassOfElement** | Explicit: cyan, off-white border | Namespace: cyan | Explicit: **bold** cyan |
| **ies:ClassOfEntity** | Explicit: cyan, **yellow border** | Namespace: cyan | Explicit: **bold** cyan, yellow border |
| **ies:ClassOfState** | Explicit: cyan, **golden border** | Namespace: cyan | Explicit: **bold** cyan, golden border |
| **ies:ClassOfEvent** | Explicit: cyan, **pink border** | Namespace: cyan | Explicit: **bold** cyan, pink border |
| **ies:TimeBoundedClass** | Explicit: cyan, white border | Namespace: cyan | Namespace: grey |

### Metaclass Hierarchy (Second Order)

| Class | ies_full | ies_core | ies_metaclass |
|-------|----------|----------|---------------|
| **ies:ClassOfClassOfElement** | Explicit: light cyan, off-white border | Namespace: cyan | Explicit: **bold** light cyan |
| **ies:ClassOfClassOfEntity** | Explicit: light cyan, **yellow border** | Namespace: cyan | Explicit: **bold** light cyan, yellow border |
| **ies:ClassOfClassOfState** | Explicit: light cyan, **golden border** | Namespace: cyan | Explicit: **bold** light cyan, golden border |
| **ies:ClassOfClassOfEvent** | Explicit: light cyan, **pink border** | Namespace: cyan | Explicit: **bold** light cyan, pink border |

### Participation Classes

| Class | ies_full | ies_core | ies_metaclass |
|-------|----------|----------|---------------|
| **ies:EventParticipant** | Explicit: #7D30D7 (purple) | Namespace: cyan | Namespace: grey |
| **ies:ActiveEventParticipant** | Explicit: #C49BF9 (light purple) | Namespace: cyan | Namespace: grey |

### Instance Styling

| Feature | ies_full | ies_core | ies_metaclass |
|---------|----------|----------|---------------|
| **Border** | #000000 (black) | #000000 (black) | #000000 (black) |
| **Fill** | #000000 (black) | #000000 (black) | #000000 (black) |
| **Text** | Inherited from class | Inherited from class | Inherited from class |

## Visual Comparison

### ies_full - Complete Palette

```
Thing/Element:     □ White (explicit)
Entity:            █ Bright yellow (explicit)
State:             █ Golden yellow (explicit)
Event:             █ Pink (explicit)
Temporal:          █ Orange (explicit)
ClassOfElement:    █ Cyan, off-white border (explicit)
ClassOfEntity:     █ Cyan, yellow border (explicit)
ClassOfState:      █ Cyan, golden border (explicit)
ClassOfEvent:      █ Cyan, pink border (explicit)
ClassOfClassOf...: █ Light cyan, inherited borders (explicit)
Participation:     █ Purple shades (explicit)
Other ies:         █ Namespace default (cyan)
```

**Result**: Every IES class has precisely defined colours. Maximum visual information.

### ies_core - Simplified

```
Thing/Element:     █ Namespace default (cyan)
Entity:            █ Bright yellow (explicit)
State:             █ Golden yellow (explicit)
Event:             █ Pink (explicit)
Temporal:          █ Orange (explicit)
All metaclasses:   █ Namespace default (cyan)
Participation:     █ Namespace default (cyan)
Other ies:         █ Namespace default (cyan)
```

**Result**: Only main hierarchies coloured. Cleaner, less busy. Good for focus.

### ies_metaclass - Type Theory Focus

```
Thing/Element:     □ Grey (muted)
Entity:            □ Pale yellow (muted)
State:             □ Pale golden (muted)
Event:             □ Pale pink (muted)
ClassOfElement:    █ Bright cyan, bold (emphasized)
ClassOfEntity:     █ Bright cyan, bold, yellow border (emphasized)
ClassOfState:      █ Bright cyan, bold, golden border (emphasized)
ClassOfEvent:      █ Bright cyan, bold, pink border (emphasized)
ClassOfClassOf...: █ Brighter cyan, bold, inherited borders (emphasized)
Other:             □ Grey (muted)
```

**Result**: Metaclasses pop. Base classes recede. Perfect for teaching powertype pattern.

## Use Case Decision Tree

```
What are you creating?
│
├─ Comprehensive documentation?
│  └─ Use: ies_full
│     Why: Shows all semantic distinctions
│
├─ Teaching metaclass concepts?
│  └─ Use: ies_metaclass
│     Why: Emphasizes type relationships
│
├─ Design discussion / brainstorming?
│  └─ Use: ies_core
│     Why: Less visual noise, focuses on main structure
│
└─ Mixed audience (technical + business)?
   └─ Use: ies_core
      Why: Simpler, more accessible
```

## Feature-by-Feature Analysis

### Border Inheritance

**ies_full**: ✅ Full inheritance  
- ClassOfEntity gets yellow border (from Entity)
- ClassOfState gets golden border (from State)
- ClassOfEvent gets pink border (from Event)

**ies_core**: ❌ No inheritance  
- All metaclasses use namespace default
- Simpler but less informative

**ies_metaclass**: ✅ Full inheritance  
- Same as ies_full
- Combined with bold styling for emphasis

**Recommendation**: Use inheritance (full or metaclass) for audiences familiar with type theory.

### Stereotype Display

**ies_full**: Optional (disabled by default)  
- Can enable via `show_stereotypes: true`
- Adds «meta» labels to metaclasses

**ies_core**: Disabled  
- Not supported in core scheme
- Keeps diagrams cleaner

**ies_metaclass**: Enabled by default  
- Shows «meta» and «meta²» labels
- Reinforces metaclass concept

**Recommendation**: Enable for teaching, disable for documentation.

### Colour Density

**ies_full**: High (18 explicit colours)  
- Every major IES class uniquely styled
- Maximum information density
- Can be overwhelming for newcomers

**ies_core**: Low (5 explicit colours)  
- Only main branches coloured
- Everything else uses namespace default
- Easier to scan quickly

**ies_metaclass**: Medium (14 explicit colours)  
- Metaclasses detailed, base classes simplified
- Good balance for type-focused diagrams

**Recommendation**: Match colour density to audience expertise.

## Combination Strategies

### Strategy 1: Start Simple, Add Detail

1. Begin with `ies_core` for initial design
2. Switch to `ies_full` for detailed documentation
3. Use `ies_metaclass` for specific type discussions

### Strategy 2: Audience-Based Selection

| Audience | Recommended Scheme | Why |
|----------|-------------------|-----|
| Business stakeholders | ies_core | Less technical, clearer |
| Software developers | ies_full | Complete information |
| Ontology engineers | ies_full | Maximum detail |
| Students/trainees | ies_metaclass | Teaching focus |
| Mixed group | ies_core | Accessible to all |

### Strategy 3: Document Type

| Document | Recommended Scheme | Why |
|----------|-------------------|-----|
| API documentation | ies_full | Complete reference |
| Tutorial | ies_metaclass | Learning focus |
| Architecture overview | ies_core | High-level view |
| Technical specification | ies_full | Precision required |
| Presentation slides | ies_core or ies_metaclass | Clear, focused |

## Performance Comparison

| Scheme | Lookup Speed | Memory | Rendering Time |
|--------|-------------|--------|----------------|
| ies_full | O(1) | High | Fast |
| ies_core | O(1) | Low | Fastest |
| ies_metaclass | O(1) | Medium | Fast |

**Conclusion**: Performance differences negligible for typical use. Choose based on visual needs, not performance.

## Customization Difficulty

| Scheme | Easy to Customize | Why |
|--------|------------------|-----|
| ies_full | Medium | Many explicit entries to maintain |
| ies_core | Easy | Few explicit entries, simple structure |
| ies_metaclass | Medium | Moderate number of entries |

**Tip**: Start by customizing ies_core, then expand to ies_full if needed.

## Example Commands

### Generate Same Context with Different Schemes

```bash
# Full detail
rdf-construct uml ies.ttl contexts.yml \
  --context entity_hierarchy \
  --style-config ies_colour_palette.yml \
  --style ies_full

# Simplified
rdf-construct uml ies.ttl contexts.yml \
  --context entity_hierarchy \
  --style-config ies_colour_palette.yml \
  --style ies_core

# Metaclass focus
rdf-construct uml ies.ttl contexts.yml \
  --context entity_hierarchy \
  --style-config ies_colour_palette.yml \
  --style ies_metaclass
```

### Compare Results

Generate all three for comparison:

```bash
for scheme in ies_full ies_core ies_metaclass; do
  rdf-construct uml ies.ttl contexts.yml \
    --context my_context \
    --style-config ies_colour_palette.yml \
    --style $scheme \
    --outdir diagrams/$scheme
done
```

Then compare the output in `diagrams/ies_full/`, `diagrams/ies_core/`, and `diagrams/ies_metaclass/`.

## Recommendations Summary

### Choose ies_full when:
- Creating reference documentation
- Audience is technically sophisticated
- Need maximum semantic information
- Working with complete IES ontology
- Creating training materials for advanced users

### Choose ies_core when:
- Presenting to mixed or non-technical audience
- Creating high-level architecture diagrams
- Want faster visual scanning
- Initial design/brainstorming sessions
- Need printable/accessible diagrams

### Choose ies_metaclass when:
- Teaching type theory or powertype pattern
- Focusing on metaclass relationships
- Creating academic papers on IES structure
- Explaining ies:ClassOf hierarchy
- Demonstrating instantiation patterns

## Migration Between Schemes

### From Core to Full

**Easy**: Just change `--style` parameter

```bash
# Before
--style ies_core

# After
--style ies_full
```

No context changes needed. All core colours are subset of full.

### From Full to Metaclass

**Medium**: May want to adjust contexts

```bash
# Before
--style ies_full

# After  
--style ies_metaclass
```

Consider: Focus contexts on metaclass relationships for best effect.

### From Core to Metaclass

**Medium**: Significant visual change

```bash
# Before
--style ies_core

# After
--style ies_metaclass
```

Consider: Add metaclass-focused contexts. Base classes will appear muted.

## Conclusion

All three schemes serve specific purposes:

- **ies_full**: Comprehensive, information-dense, precise
- **ies_core**: Simple, accessible, scannable
- **ies_metaclass**: Educational, type-focused, explanatory

Choose based on:
1. Your audience's expertise
2. The document's purpose
3. The visual complexity you can afford
4. The aspects of IES you want to emphasize

**Best Practice**: Generate examples with all three schemes, pick the one that works best for your specific use case.