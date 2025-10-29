#!/bin/bash

# POS Demo Data Import Runner Script
# This script makes it easy to run the import with the correct bench command

BENCH_DIR="/Volumes/TZARMORSP/wrk/pos/frappe-bench"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        POS Demo Data Import Script Runner            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the bench directory
if [ ! -d "$BENCH_DIR" ]; then
    echo -e "${RED}Error: Bench directory not found at $BENCH_DIR${NC}"
    exit 1
fi

cd "$BENCH_DIR" || exit 1

# Get list of sites
echo -e "${YELLOW}Available sites:${NC}"
sites=$(ls -1 sites/*/site_config.json 2>/dev/null | sed 's|sites/||' | sed 's|/site_config.json||')

if [ -z "$sites" ]; then
    echo -e "${RED}No sites found!${NC}"
    exit 1
fi

# Display sites with numbers
i=1
declare -a site_array
while IFS= read -r site; do
    echo "  $i) $site"
    site_array[$i]=$site
    ((i++))
done <<< "$sites"

echo ""

# Ask user to select a site
if [ "$#" -eq 1 ]; then
    SITE_NAME="$1"
    echo -e "${GREEN}Using site: $SITE_NAME${NC}"
else
    echo -e "${YELLOW}Enter site number or site name:${NC}"
    read -r site_input
    
    # Check if input is a number
    if [[ "$site_input" =~ ^[0-9]+$ ]]; then
        SITE_NAME="${site_array[$site_input]}"
    else
        SITE_NAME="$site_input"
    fi
fi

if [ -z "$SITE_NAME" ]; then
    echo -e "${RED}No site selected. Exiting.${NC}"
    exit 1
fi

# Check if site exists
if [ ! -f "sites/$SITE_NAME/site_config.json" ]; then
    echo -e "${RED}Error: Site '$SITE_NAME' does not exist!${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Starting import for site: ${GREEN}$SITE_NAME${NC}"
echo -e "${YELLOW}This may take several minutes depending on the amount of data...${NC}"
echo ""

# Run the import
bench --site "$SITE_NAME" execute erpnext.posdemo.import_pos_data.main

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Import Process Completed!                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║         Import Process Failed (Exit: $exit_code)          ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
fi

exit $exit_code

