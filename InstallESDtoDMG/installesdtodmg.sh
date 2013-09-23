#!/bin/bash


# Cleanup.

declare -a tempdirs
remove_tempdirs() {
    for tempdir in "${tempdirs[@]}"; do
        rm -rf "$tempdir"
    done
    return 0
}
trap remove_tempdirs EXIT


# Arguments.

if [[ $(id -u) -ne 0 ]]; then
    echo "$(basename "$0") must run as root"
    exit 1
fi

if [[ -z "$1" || -z "$2" ]]; then
    echo "Usage: $(basename "$0") OS_X_Installer.app output.dmg"
    exit 1
fi
installapp="$1"
sharedsupport="$installapp/Contents/SharedSupport"
esddmg="$sharedsupport/InstallESD.dmg"
if [[ ! -e "$esddmg" ]]; then
    echo "'$esddmg' not found" 1>&2
    exit 1
fi
compresseddmg="$2"


# Get a work directory and check free space.
tempdir=$(mktemp -d -t installesdtodmg)
tempdirs+=("$tempdir")
freespace=$(df -g / | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 10 ]]; then
    echo "Less than 10 GB free disk space, aborting"
fi


# Create and mount a sparse image.
sparsedmg="$tempdir/os.sparseimage"
sparsevolname=$(printf "Sparse%04x HD" $RANDOM)
hdiutil create -size 32g -type SPARSE -fs HFS+J -volname "$sparsevolname" "$sparsedmg"
hdiutil attach -owners on -noverify "$sparsedmg"
sparsemount="/Volumes/$sparsevolname"

# Mount the install media.
esdmount=$(hdiutil attach -nobrowse -mountrandom /tmp -noverify "$esddmg" | grep Apple_HFS | awk '{print $3}')

# Perform the OS install.
installer -verboseR -pkg "$esdmount/Packages/OSInstall.mpkg" -target "$sparsemount"

# Eject the install media.
hdiutil eject "$esdmount"

# Eject the sparse image.
hdiutil eject "$sparsemount"

# Convert the sparse image to a compressed image.
hdiutil convert -format UDZO "$sparsedmg" -o "$compresseddmg"

# Scan compressed image for restore.
asr imagescan --source "$compresseddmg"

# Change ownership to that of the containing directory.
chown $(stat -f '%u:%g' $(dirname "$compresseddmg")) "$compresseddmg"

exit 0
