#!/bin/bash

srcdir="$1"

if [ -z "$srcdir" -o ! -d "$srcdir" ]; then
    echo "Usage: $0 srcdir"
    exit 1
fi

name=`basename "$srcdir"`

echo "Cleaning"
find "$srcdir" -name .DS_Store -print0 | xargs -0 rm -f

echo "Adding documentation"
markdown ../README.markdown | cat ../README.css - | tidy -q -i > "$srcdir/$name.html"

echo "Creating image"
dmg_fname="$srcdir.dmg"
sudo -p "Password for %p@%h: " hdiutil create -srcfolder "$srcdir" -uid 0 -gid 0 -ov "$dmg_fname"
sudo -p "Password for %p@%h: " chown ${UID} "$dmg_fname"
