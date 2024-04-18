#!/bin/bash

dest="${1:-chrono-list.csv}"

echo "Video,Season,Episode,Name" > "${dest}"

curl https://www.startrekviewingguide.com/lo-fi-print-ready-listing.html | grep -E "(<li|p1 f5).*[A-Z9]{3}" | sed -E 's/.*<.*>\s*([A-Z9]{3}[^<]+)<.*/\1/g' | sed 's/ $//g' | sed -E 's/ +(- +)*/|/g'| sed -E 's/([0-9])\s*[Ee]pisode/\1| episode/g' | sed -E 's/,\s*[Ee]pisode/| episode/g' | sed -E 's/[Ss]eason\s+|\s+[Ee]pisode\s+//g' | sed 's/MOV|/MOV|||/g' | perl -n -mHTML::Entities -e ' ; print HTML::Entities::decode_entities($_) ;' >> "${dest}"
