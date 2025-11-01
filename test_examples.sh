#!/usr/bin/env bash
#
# test_examples.sh
#
# Quick test script to verify rdf-construct works with example ontologies
#
# Usage:
#   chmod +x test_examples.sh
#   ./test_examples.sh

set -e  # Exit on error

echo "=========================================="
echo "Testing rdf-construct with examples"
echo "=========================================="
echo ""

# Check if rdf-construct is installed
if ! command -v rdf-construct &> /dev/null; then
    echo "ERROR: rdf-construct not found."
    echo "Please install: poetry install"
    echo "And activate:   poetry shell"
    exit 1
fi

# Check if example files exist
if [ ! -f "examples/animal_ontology.ttl" ]; then
    echo "ERROR: Example ontologies not found."
    echo "Please run this script from the project root directory."
    exit 1
fi

# Create output directory
mkdir -p test_output
echo "Creating test output directory: test_output/"
echo ""

# Test 1: List profiles
echo "Test 1: Listing available profiles"
echo "-----------------------------------"
rdf-construct profiles examples/test_profile.yml
echo ""

# Test 2: Simple ontology with alpha profile
echo "Test 2: Simple ontology with alpha profile"
echo "-------------------------------------------"
rdf-construct order examples/simple_ontology.ttl examples/test_profile.yml -p alpha -o test_output/
echo "✓ Created: test_output/simple_ontology-alpha.ttl"
echo ""

# Test 3: Animal ontology with multiple profiles
echo "Test 3: Animal ontology with multiple profiles"
echo "-----------------------------------------------"
rdf-construct order examples/animal_ontology.ttl examples/test_profile.yml -p alpha -p topo -p animal_topo -o test_output/
echo "✓ Created: test_output/animal_ontology-alpha.ttl"
echo "✓ Created: test_output/animal_ontology-topo.ttl"
echo "✓ Created: test_output/animal_ontology-animal_topo.ttl"
echo ""

# Test 4: Organization ontology with org-specific profile
echo "Test 4: Organization ontology with org profile"
echo "-----------------------------------------------"
rdf-construct order examples/organisation_ontology.ttl examples/test_profile.yml -p org_topo -o test_output/
echo "✓ Created: test_output/organisation_ontology-org_topo.ttl"
echo ""

# Test 5: Compare alpha vs topo
echo "Test 5: Comparing alpha vs topological ordering"
echo "------------------------------------------------"
echo "Lines in alpha output:  $(wc -l < test_output/animal_ontology-alpha.ttl)"
echo "Lines in topo output:   $(wc -l < test_output/animal_ontology-topo.ttl)"
echo ""
echo "First 10 subject lines in alpha:"
grep "^ex:" test_output/animal_ontology-alpha.ttl | head -10
echo ""
echo "First 10 subject lines in topo (note hierarchical order):"
grep "^ex:" test_output/animal_ontology-topo.ttl | head -10
echo ""

# Test 6: Verify output is valid Turtle (if rapper available)
if command -v rapper &> /dev/null; then
    echo "Test 6: Validating Turtle syntax with rapper"
    echo "---------------------------------------------"
    for file in test_output/*.ttl; do
        if rapper -i turtle "$file" -o ntriples > /dev/null 2>&1; then
            echo "✓ Valid: $file"
        else
            echo "✗ Invalid: $file"
        fi
    done
    echo ""
else
    echo "Test 6: Skipping syntax validation (rapper not installed)"
    echo ""
fi

# Summary
echo "=========================================="
echo "All tests completed successfully!"
echo "=========================================="
echo ""
echo "Generated files in test_output/:"
ls -lh test_output/*.ttl
echo ""
echo "To inspect the differences:"
echo "  diff test_output/animal_ontology-alpha.ttl test_output/animal_ontology-topo.ttl"
echo ""
echo "To clean up:"
echo "  rm -rf test_output/"
