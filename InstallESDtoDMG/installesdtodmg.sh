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
    echo "IED:FAILURE:$(basename "$0") must run as root"
    exit 1
fi

if [[ -z "$1" || -z "$2" ]]; then
    echo "IED:FAILURE:Usage: $(basename "$0") OS_X_Installer.app output.dmg"
    exit 1
fi
installapp="$1"
sharedsupport="$installapp/Contents/SharedSupport"
esddmg="$sharedsupport/InstallESD.dmg"
if [[ ! -e "$esddmg" ]]; then
    echo "IED:FAILURE:'$esddmg' not found" 1>&2
    exit 1
fi
compresseddmg="$2"


# Get a work directory and check free space.
tempdir=$(mktemp -d -t installesdtodmg)
tempdirs+=("$tempdir")
freespace=$(df -g / | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 10 ]]; then
    echo "IED:FAILURE:Less than 10 GB free disk space, aborting"
    exit 1
fi


# Create and mount a sparse image.
echo "IED:MSG:Initializing DMG"
sparsedmg="$tempdir/os.sparseimage"
sparsevolname=$(printf "Sparse%04x HD" $RANDOM)
hdiutil create -size 32g -type SPARSE -fs HFS+J -volname "$sparsevolname" "$sparsedmg"
hdiutil attach -owners on -noverify "$sparsedmg"
sparsemount="/Volumes/$sparsevolname"

# Mount the install media.
echo "IED:MSG:Mounting install media"
esdmount=$(hdiutil attach -nobrowse -mountrandom /tmp -noverify "$esddmg" | grep Apple_HFS | awk '{print $3}')
if [[ ! -d "$esdmount/Packages" ]]; then
    echo "IED:FAILURE:Failed to mount install media"
    exit 101
fi

# Perform the OS install.
echo "IED:MSG:Starting OS install"
installer -verboseR -pkg "$esdmount/Packages/OSInstall.mpkg" -target "$sparsemount"
declare -i result=$?
if [[ $result -ne 0 ]]; then
    echo "IED:FAILURE:OS install failed with return code $result"
    exit 102
fi
    
# Eject the install media.
echo "IED:MSG:Ejecting install media"
hdiutil eject "$esdmount"

# Eject the sparse image.
echo "IED:MSG:Ejecting DMG"
hdiutil eject "$sparsemount"

# Convert the sparse image to a compressed image.
echo "IED:MSG:Converting DMG to read only"
if ! hdiutil convert -format UDZO "$sparsedmg" -o "$compresseddmg"; then
    echo "IED:FAILURE:DMG conversion failed"
    exit 103
fi

# Scan compressed image for restore.
echo "IED:MSG:Scanning DMG for restore"
if ! asr imagescan --source "$compresseddmg"; then
    echo "IED:FAILURE:DMG scanning failed"
    exit 104
fi

# Change ownership to that of the containing directory.
echo "IED:MSG:Changing owner"
if ! chown $(stat -f '%u:%g' $(dirname "$compresseddmg")) "$compresseddmg"; then
    echo "IED:FAILURE:Ownership change failed"
    exit 105
fi


echo "IED:MSG:Done"
echo "IED:SUCCESS:Done"

exit 0
