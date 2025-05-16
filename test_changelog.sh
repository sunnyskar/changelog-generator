#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print test header
print_test_header() {
    echo -e "\n${GREEN}=== Testing: $1 ===${NC}"
}

# Function to run test and check result
run_test() {
    echo -e "\nCommand: $1"
    eval "$1"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test passed${NC}"
    else
        echo -e "${RED}✗ Test failed${NC}"
    fi
}

# Make sure the script is executable
chmod +x changelog_generator.py

# Test 1: Basic usage with local repository
print_test_header "Basic usage with local repository"
run_test "./changelog_generator.py . 5"

# Test 2: Save output to file
print_test_header "Save output to file"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 5 -o test_changelog.md"
if [ -f "test_changelog.md" ]; then
    echo -e "${GREEN}✓ Output file created${NC}"
else
    echo -e "${RED}✗ Output file not created${NC}"
fi

# Test 3: Date filtering
print_test_header "Date filtering"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 10 --from-date 2024-01-01 --to-date 2024-12-31"

# Test 4: Author filtering
print_test_header "Author filtering"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 10 --author \"$(git config user.name)\""

# Test 5: Custom categories
print_test_header "Custom categories"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 5 -c \"New Features\" -c \"Bug Fixes\" -c \"Improvements\""

# Test 6: Exclude patterns
print_test_header "Exclude patterns"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 10 -e \"chore:\" -e \"docs:\""

# Test 7: Local URL
print_test_header "Local URL"
run_test "./changelog_generator.py ../../sp23-cs411-team099-SKY 5"

# Test 8: Combined options
print_test_header "Combined options"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 10 --from-date 2024-01-01 --author \"$(git config user.name)\" -c \"Features\" -e \"chore:\" -o combined_test.md"

# Test 9: Tag filtering (if tags exist in the repository)
print_test_header "Tag filtering"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 10 -t v4.0.0 -t v4.1.0 -t v4.2.0"

# Test 10: Preview mode
print_test_header "Preview mode"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 5 -p"

# Test 11: Interactive mode
print_test_header "Interactive mode"
# Note: This test will require manual interaction
echo "This test requires manual interaction. Please select some commits when prompted."
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 5 -i"

# Test 12: Silent mode
print_test_header "Silent mode"
run_test "./changelog_generator.py https://github.com/cloudquery/cloudquery.git 5 -s > silent_output.md"
if [ -f "silent_output.md" ]; then
    # Check if the file contains only the changelog content (starts with #)
    if grep -q "^#" silent_output.md; then
        echo -e "${GREEN}✓ Silent mode output is clean${NC}"
    else
        echo -e "${RED}✗ Silent mode output contains extra content${NC}"
    fi
else
    echo -e "${RED}✗ Silent mode output file not created${NC}"
fi

# Cleanup
echo -e "\n${GREEN}Cleaning up test files...${NC}"
rm -f test_changelog.md combined_test.md silent_output.md

echo -e "\n${GREEN}All tests completed!${NC}" 