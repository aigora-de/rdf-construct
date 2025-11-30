# IES Colour Palette Quick Reference

## Core Classes

```
┌─────────────────────┬──────────────┬──────────────┐
│ Class               │ Border       │ Fill         │
├─────────────────────┼──────────────┼──────────────┤
│ ies:Thing           │ #000000 ███  │ #FFFFFF □    │
│ ies:Element         │ #000000 ███  │ #FFFFFF □    │
│ ies:Entity          │ #968584 ███  │ #FEFE54 ▓▓▓  │ ← Yellow
│ ies:State           │ #000000 ███  │ #F7D748 ▓▓▓  │ ← Golden
│ ies:Event           │ #968584 ███  │ #F5C2CB ▓▓▓  │ ← Pink
│ ies:PeriodOfTime    │ #968584 ███  │ #F3B169 ▓▓▓  │ ← Orange
└─────────────────────┴──────────────┴──────────────┘
```

## Metaclasses (First Order)

```
┌─────────────────────────┬──────────────┬──────────────┐
│ Class                   │ Border       │ Fill         │
├─────────────────────────┼──────────────┼──────────────┤
│ ies:ClassOfElement      │ #FCFCFC □    │ #5CC9FA ▓▓▓  │ ← Cyan
│ ies:ClassOfEntity       │ #FEFE54 ▓▓▓  │ #5CC9FA ▓▓▓  │ ← Yellow border
│ ies:ClassOfState        │ #F7D748 ▓▓▓  │ #5CC9FA ▓▓▓  │ ← Golden border
│ ies:ClassOfEvent        │ #F5C2CB ▓▓▓  │ #5CC9FA ▓▓▓  │ ← Pink border
│ ies:TimeBoundedClass    │ #FFFFFF □    │ #5CC9FA ▓▓▓  │
└─────────────────────────┴──────────────┴──────────────┘
```

## Metaclasses (Second Order)

```
┌─────────────────────────────┬──────────────┬──────────────┐
│ Class                       │ Border       │ Fill         │
├─────────────────────────────┼──────────────┼──────────────┤
│ ies:ClassOfClassOfElement   │ #FCFCFC □    │ #74FAFC ▓▓▓  │ ← Light cyan
│ ies:ClassOfClassOfEntity    │ #FEFE54 ▓▓▓  │ #74FAFC ▓▓▓  │
│ ies:ClassOfClassOfState     │ #F7D748 ▓▓▓  │ #74FAFC ▓▓▓  │
│ ies:ClassOfClassOfEvent     │ #F5C2CB ▓▓▓  │ #74FAFC ▓▓▓  │
└─────────────────────────────┴──────────────┴──────────────┘
```

## Participation Classes

```
┌──────────────────────────────┬──────────────┬──────────────┐
│ Class                        │ Border       │ Fill         │
├──────────────────────────────┼──────────────┼──────────────┤
│ ies:EventParticipant         │ #000000 ███  │ #7D30D7 ▓▓▓  │ ← Dark purple
│ ies:ActiveEventParticipant   │ #000000 ███  │ #C49BF9 ▓▓▓  │ ← Light purple
└──────────────────────────────┴──────────────┴──────────────┘
```

## Instances

```
┌──────────────────┬──────────────┬──────────────┬──────────────┐
│ Type             │ Border       │ Fill         │ Text         │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ All instances    │ #000000 ███  │ #000000 ███  │ Inherited    │
└──────────────────┴──────────────┴──────────────┴──────────────┘

Text colour inherits from class hierarchy infill colour:
  • Instance of Entity → Yellow text (#FEFE54)
  • Instance of State → Golden text (#F7D748)
  • Instance of Event → Pink text (#F5C2CB)
  • Instance of ClassOfElement → Cyan text (#5CC9FA)
```

## Colour Families

```
Entity Family:       ████ #FEFE54 (bright yellow)
State Family:        ████ #F7D748 (golden yellow)
Event Family:        ████ #F5C2CB (pink)
Temporal Family:     ████ #F3B169 (orange)
Metaclass (1st):     ████ #5CC9FA (cyan)
Metaclass (2nd):     ████ #74FAFC (light cyan)
Participation:       ████ #7D30D7 / #C49BF9 (purple shades)
```

## Border Inheritance Pattern

```
Base Class                Metaclass
─────────────────────────────────────────────
Entity (#FEFE54)    →     ClassOfEntity (border: #FEFE54)
State (#F7D748)     →     ClassOfState (border: #F7D748)
Event (#F5C2CB)     →     ClassOfEvent (border: #F5C2CB)
```

## RGB Values

```yaml
# Core Hierarchy
Thing/Element:     0, 0, 0      → 255, 255, 255  (black → white)
Entity:            150, 133, 132 → 254, 254, 84   (grey-brown → yellow)
State:             0, 0, 0      → 247, 215, 72   (black → golden)
Event:             150, 133, 132 → 245, 194, 203  (grey-brown → pink)
PeriodOfTime:      150, 133, 132 → 243, 177, 105  (grey-brown → orange)

# Metaclasses (1st order)
ClassOfElement:    252, 252, 252 → 92, 201, 250   (off-white → cyan)
ClassOfEntity:     254, 254, 84  → 92, 201, 250   (yellow → cyan)
ClassOfState:      247, 215, 72  → 92, 201, 250   (golden → cyan)
ClassOfEvent:      245, 194, 203 → 92, 201, 250   (pink → cyan)

# Metaclasses (2nd order)
All ClassOfClassOf: [inherit border] → 116, 250, 252 (light cyan)

# Participation
EventParticipant:        0, 0, 0 → 125, 48, 215   (black → dark purple)
ActiveEventParticipant:  0, 0, 0 → 196, 155, 249  (black → light purple)
```

## Usage

```bash
# Full IES scheme
rdf-construct uml ies.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_full

# Core hierarchy only
rdf-construct uml ies.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_core

# Metaclass emphasis
rdf-construct uml ies.ttl contexts.yml \
  --style-config ies_colour_palette.yml \
  --style ies_metaclass
```

## Visual Legend

```
Classes:
  ┌─────────────────┐
  │  ies:Entity     │  ← Coloured border & fill
  │                 │  ← Black text
  │  +property      │
  └─────────────────┘

Instances:
  ┌─────────────────┐
  │  my:alice       │  ← Black border & fill
  │                 │  ← Coloured text (class colour)
  │  prop = value   │
  └─────────────────┘

Relationships:
  Parent ──────▷ Child      (subclass: bold black)
  Instance ····▷ Class      (rdf:type: dashed black)
  Domain ──────▷ Range      (property: solid grey)
```

## Design Intent

1. **Hierarchy Recognition**: Colour = semantic branch
2. **Metaclass Connection**: Border inherits from classified hierarchy
3. **Level Indication**: Lighter shades = higher metalevel
4. **Instance Clarity**: Black base + coloured text = "this is data, not schema"

---

**Print this page** for quick reference during ontology design sessions.