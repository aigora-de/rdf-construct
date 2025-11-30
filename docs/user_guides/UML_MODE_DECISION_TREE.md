# Selection Mode Visual Comparison

## Default Mode vs Explicit Mode

### Default Mode: Automatic Selection

```yaml
context_name:
  mode: default  # Optional, this is default
  root_classes:
    - ex:Animal
  include_descendants: true
  max_depth: 2
  properties:
    mode: domain_based
```

**What Happens:**
```
1. Start: ex:Animal
2. Find descendants (depth 2):
   - Level 1: ex:Mammal, ex:Bird
   - Level 2: ex:Dog, ex:Cat, ex:Eagle, ex:Sparrow
3. Find properties where domain in selected classes:
   - ex:hasParent, ex:eats, ex:livesIn, ex:averageWeight, ex:lifespan
4. Result: 7 classes, 5 properties (automatic)
```

**Diagram Output:**
```
     Animal
     /    \
  Mammal  Bird
   / \     / \
 Dog Cat Eagle Sparrow
```

### Explicit Mode: Manual Selection

```yaml
context_name:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Dog      # From mammal branch
    - ex:Eagle    # From bird branch
  object_properties:
    - ex:hasParent
  datatype_properties:
    - ex:lifespan
```

**What Happens:**
```
1. Use exactly specified classes: ex:Animal, ex:Dog, ex:Eagle
2. Use exactly specified properties: ex:hasParent, ex:lifespan
3. No traversal, no inference, no automatic selection
4. Result: 3 classes, 2 properties (manual)
```

**Diagram Output:**
```
   Animal
   /    \
 Dog    Eagle
```

## Use Case Comparison

### Use Case 1: Complete Hierarchy

**Goal**: Show entire animal taxonomy.

**Default Mode** (Better):
```yaml
complete:
  root_classes: [ex:Animal]
  include_descendants: true
  properties:
    mode: domain_based
```
✅ Concise  
✅ Auto-updates with ontology  

**Explicit Mode**:
```yaml
complete:
  mode: explicit
  classes:
    - ex:Animal
    - ex:Mammal
    - ex:Bird
    - ex:Dog
    - ex:Cat
    - ex:Eagle
    - ex:Sparrow
  # ... all properties listed
```
❌ Verbose  
❌ Must update manually  

**Winner**: Default mode

---

### Use Case 2: Cross-Branch Selection

**Goal**: Show Dog (from mammals) and Eagle (from birds).

**Default Mode**:
```yaml
cross_branch:
  focus_classes:
    - ex:Dog
    - ex:Eagle
  properties:
    mode: domain_based
```
⚠️ Gets ALL domain-based properties  
⚠️ Can't easily limit to specific properties  

**Explicit Mode** (Better):
```yaml
cross_branch:
  mode: explicit
  classes:
    - ex:Animal  # Common ancestor
    - ex:Dog
    - ex:Eagle
  object_properties:
    - ex:hasParent  # Only this relationship
  datatype_properties:
    - ex:lifespan
```
✅ Precise control  
✅ Only specified properties  
✅ Clean cross-branch view  

**Winner**: Explicit mode

---

### Use Case 3: Partial Hierarchy

**Goal**: Show Mammal with direct subclasses only (depth 1).

**Default Mode**:
```yaml
partial:
  root_classes: [ex:Mammal]
  include_descendants: true
  max_depth: 1
  properties:
    mode: domain_based
```
✅ Concise  
⚠️ Inflexible if you want different depths in different branches  

**Explicit Mode**:
```yaml
partial:
  mode: explicit
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
  # Stop here - no deeper
  object_properties:
    - ex:hasParent
```
✅ Precise control over depth  
✅ Can vary depth per branch  
⚠️ More verbose  

**Winner**: Tie (depends on needs)

---

### Use Case 4: Themed View (Predation Only)

**Goal**: Show only predator-prey relationships.

**Default Mode**:
```yaml
themed:
  focus_classes:
    - ex:Dog
    - ex:Cat
    - ex:Sparrow
  properties:
    mode: explicit
    include: [ex:eats]
```
⚠️ Mixed approach (focus + explicit props)  
✅ Works, but not intuitive  

**Explicit Mode** (Better):
```yaml
themed:
  mode: explicit
  classes:
    - ex:Dog
    - ex:Cat
    - ex:Sparrow
  object_properties:
    - ex:eats  # Only predation
  datatype_properties: []
```
✅ Clear intent  
✅ Consistent approach  
✅ Easy to understand  

**Winner**: Explicit mode

## Decision Tree

```
┌─────────────────────────────────────┐
│ Do you need concepts from           │
│ multiple unrelated hierarchies?     │
└─────────────┬───────────────────────┘
              │
        ┌─────┴─────┐
        │           │
       Yes         No
        │           │
        ▼           ▼
   EXPLICIT    ┌───────────────────────┐
    MODE       │ Do you want complete  │
               │ branch(es)?           │
               └─────┬─────────────────┘
                     │
               ┌─────┴─────┐
               │           │
              Yes         No
               │           │
               ▼           ▼
          DEFAULT     ┌────────────────┐
           MODE       │ Is standard    │
                      │ property mode  │
                      │ sufficient?    │
                      └────┬───────────┘
                           │
                     ┌─────┴─────┐
                     │           │
                    Yes         No
                     │           │
                     ▼           ▼
                 DEFAULT    EXPLICIT
                  MODE        MODE
```

## Configuration Size Comparison

### Default Mode
```yaml
# 6 lines
mammals:
  root_classes: [ex:Mammal]
  include_descendants: true
  max_depth: 1
  properties:
    mode: domain_based
```

### Explicit Mode (Equivalent)
```yaml
# 13 lines
mammals:
  mode: explicit
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
    - ex:Horse
  object_properties:
    - ex:hasParent
    - ex:eats
  datatype_properties:
    - ex:averageWeight
    - ex:lifespan
```

**Trade-off**: 2x longer but more explicit about what's included.

## Ontology Evolution

### Default Mode
```yaml
mammals:
  root_classes: [ex:Mammal]
  include_descendants: true
```

**Ontology changes**:
- Add `ex:Elephant` class → Automatically included ✅
- Add `ex:habitat` property → Automatically included ✅
- Config stays current without updates

### Explicit Mode
```yaml
mammals:
  mode: explicit
  classes:
    - ex:Mammal
    - ex:Dog
    - ex:Cat
```

**Ontology changes**:
- Add `ex:Elephant` class → NOT included ❌
- Add `ex:habitat` property → NOT included ❌
- Must update config manually

**Trade-off**: Stability vs auto-adjustment.

## When Each Mode Excels

### Default Mode Excels
- ✅ Complete hierarchies
- ✅ Standard property modes work
- ✅ Ontology changes frequently
- ✅ Want concise config
- ✅ Single hierarchy branch
- ✅ Quick prototyping

### Explicit Mode Excels
- ✅ Cross-branch concepts
- ✅ Partial hierarchies
- ✅ Thematic/subject views
- ✅ Precise control needed
- ✅ Stable ontology subset
- ✅ Document exactly what's shown
- ✅ Mix unrelated concepts

## Quick Reference

| Feature | Default | Explicit |
|---------|---------|----------|
| **Config Size** | Small | Large |
| **Precision** | Good | Excellent |
| **Maintenance** | Auto | Manual |
| **Cross-branch** | Hard | Easy |
| **Learning Curve** | Low | Medium |
| **Best For** | Hierarchies | Custom views |

## Example: Same Ontology, Different Needs

Given this ontology:
```
Animal
├── Mammal
│   ├── Dog
│   └── Cat
└── Bird
    ├── Eagle
    └── Sparrow
```

### Need 1: Complete Taxonomy
```yaml
complete:
  root_classes: [ex:Animal]
  include_descendants: true
```
**Use**: Default mode (4 lines)

### Need 2: Mammals Only
```yaml
mammals:
  root_classes: [ex:Mammal]
  include_descendants: true
```
**Use**: Default mode (4 lines)

### Need 3: One From Each Branch
```yaml
samples:
  mode: explicit
  classes: [ex:Dog, ex:Eagle]
```
**Use**: Explicit mode (5 lines, but only way to do it cleanly)

### Need 4: Predation Network
```yaml
predation:
  mode: explicit
  classes: [ex:Dog, ex:Cat, ex:Eagle, ex:Sparrow]
  object_properties: [ex:eats]
```
**Use**: Explicit mode (7 lines, clear intent)

## Summary

**Default Mode**: Great for hierarchies, concise, auto-adjusting  
**Explicit Mode**: Great for precision, cross-branch, themed views  

**Best Practice**: Use default mode by default, switch to explicit mode when you need precise control.

**Hybrid Approach** (Future): Combine both for best of both worlds.