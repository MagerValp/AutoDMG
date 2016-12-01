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
#   installesdtodmg.sh user group output.dmg "Macintosh HD" 32 /tmp/template.adtmpl \
#       "/Volumes/OS X Install ESD/Packages/OSInstall.mpkg" [package.pkg ...]


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
    echo "IED:FAILURE:Usage: $(basename "$0") user group output.dmg volname size OSInstall.mpkg [package...]"
    exit 100
fi
user="$1"
group="$2"
compresseddmg="$3"
volname="$4"
size="$5"
template="$6"
if [[ "$7" == *.dmg ]]; then
    sysimg="$7"
    shift 7
else
    shift 6
fi

# Get a work directory and check free space.
tempdir=$(mktemp -d "${TMPDIR:-/tmp/}installesdtodmg.XXXXXXXX")
tempdirs+=("$tempdir")
freespace=$(df -g "$tempdir" | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 15 ]]; then
    echo "IED:FAILURE:Less than 15 GB free disk space, aborting"
    exit 100
fi


# Create and mount a sparse image.
echo "IED:PHASE:sparseimage"
echo "IED:MSG:Creating disk image"
if [[ -z "$sysimg" ]]; then
    sparsedmg="$tempdir/os.sparseimage"
    hdiutil create -size "${size}g" -type SPARSE -fs HFS+J -volname "$volname" -uid 0 -gid 80 -mode 1775 "$sparsedmg"
    sparsemount=$(hdiutil attach -nobrowse -noautoopen -noverify -owners on "$sparsedmg" | grep Apple_HFS | cut -f3)
else
    shadowfile="$tempdir/autodmg.shadow"
    shadowdev=$(hdiutil attach -shadow "$shadowfile" -nobrowse -noautoopen -noverify -owners on "$sysimg" \
                | grep Apple_HFS \
                | awk '{print $1}')
    echo "IED:MSG:Renaming $shadowdev to $volname"
    echo "IED:MSG:Renaming volume"
    diskutil rename "$shadowdev" "$volname"
    sparsemount=$(hdiutil info | grep "^$shadowdev" | cut -f3)
fi
dmgmounts+=("$sparsemount")

# Install OS and packages.
export COMMAND_LINE_INSTALL=1
export CM_BUILD=CM_BUILD
declare -i pkgnum=0
# Start watching /var/log/install.log.
echo "IED:WATCHLOG:START"
for package; do
    echo "IED:PHASE:install $pkgnum:$package"
    let pkgnum++
    echo "IED:MSG:Installing $(basename "$package")"
    if [[ "${package##*.}" == "app" ]]; then
        appname="${package##*/}"
        apppath="$sparsemount/Applications/$appname"
        echo "installer:PHASE:Copying $appname"
        echo "installer:%5.0"
        ditto --noqtn --noacl "$package" "$apppath"
        echo "installer:PHASE:Changing ownership"
        echo "installer:%95.0"
        chown -hR root:admin "$apppath"
        echo "installer:PHASE:"
        echo "installer:%100.0"
    else
        if [[ $TESTING == "yes" ]]; then
            sleep 0.25
            echo "installer:PHASE:Faking it   "
            echo "installer:%25.0"
            sleep 0.25
            echo "installer:PHASE:Faking it.  "
            echo "installer:%50.0"
            sleep 0.25
            echo "installer:PHASE:Faking it.. "
            echo "installer:%75.0"
            sleep 0.25
            echo "installer:PHASE:Faking it..."
            echo "installer:%100.0"
            sleep 0.25
        else
            installer -verboseR -dumplog -pkg "$package" -target "$sparsemount"
            declare -i result=$?
            if [[ $result -ne 0 ]]; then
                echo "IED:FAILURE:$(basename "$package") failed with return code $result"
                exit 102
            fi
        fi
        # Detect system language on 10.10+. Default to Finnish if detection fails.
        if [[ $(sw_vers -productVersion | cut -d. -f2) -ge 10 ]]; then
            if [[ $(basename "$package") == "OSInstall.mpkg" ]]; then
                mkdir -p -m 0755 "$sparsemount/private/var/log"
                chown root:wheel "$sparsemount/private"
                chown root:wheel "$sparsemount/private/var"
                chown root:wheel "$sparsemount/private/var/log"
                if lang=$(python -c "from Foundation import NSLocale, NSLocaleLanguageCode; print NSLocale.currentLocale()[NSLocaleLanguageCode]" 2>/dev/null); then
                    echo "LANGUAGE=$lang" > "$sparsemount/private/var/log/CDIS.custom"
                    echo "IED:MSG:Setup Assistant language set to '$lang'"
                else
                    echo "IED:MSG:Failed to retrieve language preference, setting Setup Assistant to Finnish"
                    echo "LANGUAGE=fi" > "$sparsemount/private/var/log/CDIS.custom"
                fi
                chown root:wheel "$sparsemount/private/var/log/CDIS.custom"
            fi
        fi
    fi
done
# Stop watching /var/log/install.log.
echo "IED:WATCHLOG:STOP"

# Copy template.
mkdir -p "$sparsemount/private/var/log"
rm -f "$sparsemount/private/var/log"/*.adtmpl
cp "$template" "$sparsemount/private/var/log"

# Finalize image.
echo "IED:PHASE:asr"

# Eject the dmgs.
echo "IED:MSG:Ejecting image"
unmount_dmgs

# Convert the sparse image to a compressed image.
echo "IED:MSG:Converting disk image to read only"
if [[ -z "$sysimg" ]]; then
    hdiutil convert -puppetstrings -format UDZO "$sparsedmg" -o "$compresseddmg"
else
    hdiutil convert -puppetstrings -format UDZO -shadow "$shadowfile" "$sysimg" -o "$compresseddmg"
fi
if [[ $? -ne 0 ]]; then
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
