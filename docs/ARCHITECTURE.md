# rdf-construct Architecture

## System Architecture Diagram

```mermaid
graph TB
    subgraph "CLI Layer"
        CLI[cli.py<br/>Click Commands]
    end
    
    subgraph "Core Modules"
        CONFIG[config.py<br/>YAML Loading<br/>Dataclasses]
        PROFILE[profile.py<br/>OrderingConfig<br/>Profile Management]
        SELECTOR[selector.py<br/>Subject Selection<br/>Classes/Props/Indiv]
        ORDERING[ordering.py<br/>Topological Sort<br/>Root-Based Ordering]
        SERIALIZER[serializer.py<br/>Custom Turtle Writer<br/>Preserves Order]
        UTILS[utils.py<br/>CURIE Expansion<br/>QName Sorting]
    end
    
    subgraph "External"
        YAML[YAML Config File<br/>ontology_order.yml]
        TTL[RDF Turtle File<br/>ontology.ttl]
        OUTPUT[Output Files<br/>ontology-profile.ttl]
    end
    
    subgraph "Dependencies"
        RDFLIB[rdflib<br/>RDF Parsing]
        PYYAML[pyyaml<br/>YAML Parser]
        CLICK[click<br/>CLI Framework]
    end
    
    CLI --> PROFILE
    CLI --> CONFIG
    CLI --> SELECTOR
    CLI --> ORDERING
    CLI --> SERIALIZER
    CLI --> UTILS
    
    PROFILE --> CONFIG
    ORDERING --> UTILS
    SERIALIZER --> UTILS
    
    CONFIG --> PYYAML
    PROFILE --> PYYAML
    SELECTOR --> RDFLIB
    ORDERING --> RDFLIB
    SERIALIZER --> RDFLIB
    CLI --> CLICK
    
    YAML --> CONFIG
    TTL --> RDFLIB
    SERIALIZER --> OUTPUT
    
    style CLI fill:#e1f5ff
    style CONFIG fill:#fff4e1
    style PROFILE fill:#fff4e1
    style SELECTOR fill:#e8f5e9
    style ORDERING fill:#e8f5e9
    style SERIALIZER fill:#f3e5f5
    style UTILS fill:#fce4ec
    style YAML fill:#f5f5f5
    style TTL fill:#f5f5f5
    style OUTPUT fill:#f5f5f5
```

## Data Flow: Order Command

```mermaid
sequenceDiagram
    participant User
    participant CLI as cli.py
    participant Config as config.py
    participant Profile as profile.py
    participant RDFLib as rdflib.Graph
    participant Selector as selector.py
    participant Ordering as ordering.py
    participant Serializer as serializer.py
    participant Output as .ttl files
    
    User->>CLI: rdf-construct order ontology.ttl order.yml
    CLI->>Config: load_ordering_spec(order.yml)
    Config->>Config: Parse YAML
    Config->>Profile: Create OrderingConfig
    Profile-->>CLI: config object
    
    CLI->>RDFLib: parse(ontology.ttl)
    RDFLib-->>CLI: graph
    
    loop For each profile
        CLI->>Profile: get_profile(name)
        Profile-->>CLI: profile object
        
        loop For each section
            CLI->>Selector: select_subjects(graph, selector_key)
            Selector->>RDFLib: Query by type
            RDFLib-->>Selector: Subject URIRefs
            Selector-->>CLI: selected subjects
            
            CLI->>Ordering: sort_subjects(subjects, mode, roots)
            Ordering->>Ordering: Topological sort
            Ordering-->>CLI: ordered subjects
            
            CLI->>CLI: Accumulate ordered_subjects
        end
        
        CLI->>Serializer: build_section_graph(graph, ordered_subjects)
        Serializer-->>CLI: filtered graph
        
        CLI->>Serializer: serialize_turtle(graph, ordered_subjects, path)
        Serializer->>Serializer: Format with preserved order
        Serializer->>Output: Write ontology-profile.ttl
        Output-->>User: Generated file
    end
```

## Module Dependencies

```mermaid
graph LR
    CLI[cli.py]
    INIT[__init__.py]
    CONFIG[config.py]
    PROFILE[profile.py]
    SELECTOR[selector.py]
    ORDERING[ordering.py]
    SERIALIZER[serializer.py]
    UTILS[utils.py]
    
    CLI --> INIT
    INIT --> CONFIG
    INIT --> PROFILE
    INIT --> SELECTOR
    INIT --> ORDERING
    INIT --> SERIALIZER
    INIT --> UTILS
    
    ORDERING --> UTILS
    SERIALIZER --> UTILS
    
    style CLI fill:#4fc3f7
    style INIT fill:#81c784
    style CONFIG fill:#ffb74d
    style PROFILE fill:#ffb74d
    style SELECTOR fill:#aed581
    style ORDERING fill:#aed581
    style SERIALIZER fill:#ba68c8
    style UTILS fill:#f48fb1
```

## Ordering Algorithm Flow

```mermaid
flowchart TD
    START[Input: Graph + Subjects + Mode]
    
    MODE{Sort Mode?}
    
    ALPHA[Alphabetical Sort]
    ALPHA_OUT[Return: Sorted by QName]
    
    TOPO{Has Roots?}
    
    SIMPLE_TOPO[Simple Topological]
    SIMPLE_OUT[Return: Parents before children]
    
    ROOT_TOPO[Root-Based Topological]
    
    EXPAND[Expand root CURIEs to IRIs]
    
    LOOP_START[For each root]
    DESCENDANTS[Find all descendants]
    TOPO_BRANCH[Topological sort branch]
    APPEND[Append to output]
    LOOP_END{More roots?}
    
    REMAINING[Topological sort remaining]
    ROOT_OUT[Return: Roots first, then rest]
    
    START --> MODE
    MODE -->|alpha| ALPHA
    ALPHA --> ALPHA_OUT
    
    MODE -->|topological| TOPO
    TOPO -->|No| SIMPLE_TOPO
    SIMPLE_TOPO --> SIMPLE_OUT
    
    TOPO -->|Yes| ROOT_TOPO
    ROOT_TOPO --> EXPAND
    EXPAND --> LOOP_START
    LOOP_START --> DESCENDANTS
    DESCENDANTS --> TOPO_BRANCH
    TOPO_BRANCH --> APPEND
    APPEND --> LOOP_END
    LOOP_END -->|Yes| LOOP_START
    LOOP_END -->|No| REMAINING
    REMAINING --> ROOT_OUT
    
    style START fill:#e3f2fd
    style MODE fill:#fff9c4
    style TOPO fill:#fff9c4
    style ALPHA fill:#c8e6c9
    style SIMPLE_TOPO fill:#c8e6c9
    style ROOT_TOPO fill:#f8bbd0
    style ALPHA_OUT fill:#b2dfdb
    style SIMPLE_OUT fill:#b2dfdb
    style ROOT_OUT fill:#b2dfdb
```

## Refactoring Map

```mermaid
graph TB
    subgraph "Original: order_turtle.py (325 lines)"
        ORIG[Monolithic Script]
        ORIG_YAML[YAML helpers]
        ORIG_CURIE[CURIE/prefix helpers]
        ORIG_SELECT[Selection logic]
        ORIG_ORDER[Ordering algorithms]
        ORIG_SERIAL[Serialization]
        ORIG_MAIN[Main/CLI]
        
        ORIG --> ORIG_YAML
        ORIG --> ORIG_CURIE
        ORIG --> ORIG_SELECT
        ORIG --> ORIG_ORDER
        ORIG --> ORIG_SERIAL
        ORIG --> ORIG_MAIN
    end
    
    subgraph "Refactored: rdf-construct package (~1000 lines)"
        NEW_PKG[Package Structure]
        NEW_CONFIG[config.py<br/>193 lines]
        NEW_PROFILE[profile.py<br/>111 lines]
        NEW_UTILS[utils.py<br/>90 lines]
        NEW_SELECTOR[selector.py<br/>65 lines]
        NEW_ORDERING[ordering.py<br/>220 lines]
        NEW_SERIALIZER[serializer.py<br/>168 lines]
        NEW_CLI[cli.py<br/>174 lines]
        
        NEW_PKG --> NEW_CONFIG
        NEW_PKG --> NEW_PROFILE
        NEW_PKG --> NEW_UTILS
        NEW_PKG --> NEW_SELECTOR
        NEW_PKG --> NEW_ORDERING
        NEW_PKG --> NEW_SERIALIZER
        NEW_PKG --> NEW_CLI
    end
    
    ORIG_YAML -.->|Refactored to| NEW_CONFIG
    ORIG_YAML -.->|Refactored to| NEW_PROFILE
    ORIG_CURIE -.->|Refactored to| NEW_UTILS
    ORIG_SELECT -.->|Refactored to| NEW_SELECTOR
    ORIG_ORDER -.->|Refactored to| NEW_ORDERING
    ORIG_SERIAL -.->|Refactored to| NEW_SERIALIZER
    ORIG_MAIN -.->|Refactored to| NEW_CLI
    
    style ORIG fill:#ffebee
    style NEW_PKG fill:#e8f5e9
    style NEW_CONFIG fill:#fff9c4
    style NEW_PROFILE fill:#fff9c4
    style NEW_UTILS fill:#f8bbd0
    style NEW_SELECTOR fill:#c8e6c9
    style NEW_ORDERING fill:#c8e6c9
    style NEW_SERIALIZER fill:#e1bee7
    style NEW_CLI fill:#bbdefb
```

## Configuration Processing

```mermaid
flowchart LR
    YAML[YAML Config File]
    LOAD[load_ordering_spec]
    SPEC[OrderingSpec Object]
    
    DEFAULTS[defaults dict]
    SELECTORS[selectors dict]
    PREFIX[prefix_order list]
    PROFILES[profiles dict]
    
    PROF_OBJ[OrderingProfile Objects]
    SECTION[SectionConfig Objects]
    
    YAML --> LOAD
    LOAD --> SPEC
    
    SPEC --> DEFAULTS
    SPEC --> SELECTORS
    SPEC --> PREFIX
    SPEC --> PROFILES
    
    PROFILES --> PROF_OBJ
    PROF_OBJ --> SECTION
    
    style YAML fill:#f5f5f5
    style LOAD fill:#ffb74d
    style SPEC fill:#81c784
    style PROF_OBJ fill:#64b5f6
    style SECTION fill:#9575cd
```

## Key Insights

### Module Responsibilities

1. **config.py / profile.py** - Configuration management
   - Parse YAML into typed Python objects
   - Validate structure
   - Provide access to profiles

2. **selector.py** - Subject identification
   - Query graph for specific types
   - Handle both owl:Class and rdfs:Class
   - Identify individuals (non-classes, non-properties)

3. **ordering.py** - Sorting algorithms
   - Topological sort (Kahn's algorithm)
   - Root-based branch ordering
   - Alphabetical fallback

4. **serializer.py** - Custom output
   - **Critical**: Preserves subject order
   - Formats as valid Turtle
   - Orders predicates (rdf:type first)

5. **utils.py** - Supporting functions
   - CURIE expansion
   - QName sorting keys
   - Prefix rebinding

6. **cli.py** - User interface
   - Command definitions
   - Argument parsing
   - Progress messages

### Data Flow Summary

1. User invokes CLI command
2. YAML config loaded and parsed into dataclasses
3. RDF graph parsed by rdflib
4. For each profile:
   - For each section:
     - Select subjects by type
     - Sort subjects by mode
     - Accumulate ordered list
   - Build filtered graph
   - Serialize with preserved order
5. Output written to file

### Critical Differences from rdflib

**rdflib's default behavior:**
- Always sorts subjects alphabetically
- Loses semantic structure
- Makes diffs noisy

**Our custom serializer:**
- Respects exact subject order provided
- Preserves hierarchy in output
- Makes RDF files human-readable

This is why `serializer.py` is essential - rdflib cannot do what we need.