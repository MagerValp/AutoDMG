#!/bin/bash
#
# This script performs the main steps needed to create a deployment image:
#
#    1. Create a new read/write sparse disk image.
#    2. Install a list of packages, starting with the OS install, with the
#       sparse image as the target.
#    3. Convert the sparse disk to a read only compressed image.
#
# The generated image will need to be scanned with asr before it can be used
# for deployment.
#
# Usage (mount InstallESD.dmg first):
#
#   installesdtodmg.sh user group output.dmg "/Volumes/OS X Install ESD/Packages/OSInstall.mpkg" [package.pkg ...]


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
    exit 100
fi

if [[ $# -lt 4 ]]; then
    echo "IED:FAILURE:Usage: $(basename "$0") user group output.dmg OSInstall.mpkg [package...]"
    exit 100
fi
user="$1"
group="$2"
compresseddmg="$3"
shift 3

# Get a work directory and check free space.
tempdir=$(mktemp -d -t installesdtodmg)
tempdirs+=("$tempdir")
freespace=$(df -g / | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 15 ]]; then
    echo "IED:FAILURE:Less than 15 GB free disk space, aborting"
    exit 100
fi


# Create and mount a sparse image.
echo "IED:PHASE:sparseimage"
echo "IED:MSG:Creating disk image"
sparsedmg="$tempdir/os.sparseimage"
hdiutil create -size 32g -type SPARSE -fs HFS+J -volname "Macintosh HD" -uid 0 -gid 80 -mode 1775 "$sparsedmg"
sparsemount=$(hdiutil attach -nobrowse -noautoopen -noverify -owners on "$sparsedmg" | grep Apple_HFS | cut -f3)
dmgmounts+=("$sparsemount")

# Install OS and packages.
export COMMAND_LINE_INSTALL=1
declare -i pkgnum=0
for package; do
    echo "IED:PHASE:install $pkgnum:$package"
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
        installer -verboseR -dumplog -pkg "$package" -target "$sparsemount"
        declare -i result=$?
        if [[ $result -ne 0 ]]; then
            if [[ $pkgnum -eq 1 ]]; then
                pkgname="OS install"
            else
                pkgname=$(basename "$package")
            fi
            echo "IED:FAILURE:$pkgname failed with return code $result"
            exit 102
        fi
    fi
done

# Finalize image.
echo "IED:PHASE:asr"

# Eject the dmgs.
echo "IED:MSG:Ejecting image"
unmount_dmgs

# Convert the sparse image to a compressed image.
echo "IED:MSG:Converting disk image to read only"
if ! hdiutil convert -puppetstrings -format UDZO "$sparsedmg" -o "$compresseddmg"; then
    echo "IED:FAILURE:Disk image conversion failed"
    exit 103
fi

# Change ownership.
echo "IED:MSG:Changing owner"
if ! chown "${user}:$group" "$compresseddmg"; then
    echo "IED:FAILURE:Ownership change failed"
    exit 105
fi

exit 0
