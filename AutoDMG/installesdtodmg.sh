#!/bin/bash


declare -r TESTING="no"


# Cleanup.

declare -a tempdirs
remove_tempdirs() {
    for tempdir in "${tempdirs[@]}"; do
        rm -rf "$tempdir"
    done
    unset tempdirs
}

eject_dmg() {
    local mountpath="$1"
    if [[ -d "$mountpath" ]]; then
        if ! hdiutil eject "$mountpath"; then
            for tries in {1..10}; do
                sleep $tries
                if hdiutil eject "$mountpath" -force 2>/dev/null; then
                    break
                fi
            done
        fi
    fi
}

declare -a dmgmounts
unmount_dmgs() {
    for mountpath in "${dmgmounts[@]}"; do
        eject_dmg "$mountpath"
    done
    unset dmgmounts
}

perform_cleanup() {
    remove_tempdirs
    unmount_dmgs
    return 0
}
trap perform_cleanup EXIT


# Arguments.

if [[ $(id -u) -ne 0 ]]; then
    echo "IED:FAILURE:$(basename "$0") must run as root"
    exit 1
fi

if [[ $# -lt 4 ]]; then
    echo "IED:FAILURE:Usage: $(basename "$0") user group output.dmg OSInstall.mpkg [package...]"
    exit 1
fi
user="$1"
group="$2"
compresseddmg="$3"
shift 3

# Get a work directory and check free space.
tempdir=$(mktemp -d -t installesdtodmg)
tempdirs+=("$tempdir")
freespace=$(df -g / | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 10 ]]; then
    echo "IED:FAILURE:Less than 10 GB free disk space, aborting"
    exit 1
fi


# Create and mount a sparse image.
echo "IED:MSG:Initializing disk image"
sparsedmg="$tempdir/os.sparseimage"
hdiutil create -size 32g -type SPARSE -fs HFS+J -volname "Macintosh HD" -uid 0 -gid 80 -mode 1775 "$sparsedmg"
sparsemount=$(hdiutil attach -nobrowse -noautoopen -noverify -owners on "$sparsedmg" | grep Apple_HFS | cut -f3)
dmgmounts+=("$sparsemount")

# Perform the OS install.
declare -i pkgnum=0
for package; do
    echo "selecting package $pkgnum $package"
    echo "IED:PACKAGE:$pkgnum:$package"
    let pkgnum++
    if [[ $pkgnum -eq 1 ]]; then
        echo "IED:MSG:Starting OS install"
    else
        echo "IED:MSG:Installing $(basename "$package")"
    fi
    if [[ $TESTING == "yes" ]]; then
        sleep 1
        echo "installer:PHASE:Faking it   "
        echo "installer:%25.0"
        sleep 1
        echo "installer:PHASE:Faking it.  "
        echo "installer:%50.0"
        sleep 1
        echo "installer:PHASE:Faking it.. "
        echo "installer:%75.0"
        sleep 1
        echo "installer:PHASE:Faking it..."
        echo "installer:%100.0"
        sleep 1
    else
        installer -verboseR -pkg "$package" -target "$sparsemount"
        declare -i result=$?
        if [[ $result -ne 0 ]]; then
            echo "IED:FAILURE:OS install failed with return code $result"
            exit 102
        fi
    fi
done

# Eject the dmgs.
echo "IED:MSG:Ejecting image"
unmount_dmgs

# Convert the sparse image to a compressed image.
echo "IED:MSG:Converting disk image to read only"
if ! hdiutil convert -format UDZO "$sparsedmg" -o "$compresseddmg"; then
    echo "IED:FAILURE:Disk image conversion failed"
    exit 103
fi

# Change ownership to that of the containing directory.
echo "IED:MSG:Changing owner"
if ! chown "${user}:$group" "$compresseddmg"; then
    echo "IED:FAILURE:Ownership change failed"
    exit 105
fi

exit 0
