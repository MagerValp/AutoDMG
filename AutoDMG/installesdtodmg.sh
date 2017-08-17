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
#   installesdtodmg.sh ladmin staff HFS+J output.dmg "Macintosh HD" 32 \
#       /tmp/template.adtmpl \
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

unmount_volume() {
    local mountvolume="$1"
    local result="failure"
    if [[ -d "$mountvolume" ]]; then
        if ! diskutil unmountDisk "$mountvolume"; then
            for tries in {1..10}; do
                if [[ -d "$mountvolume" ]]; then
                    echo "IED:MSG:Unmounting '$mountvolume' failed, force attempt $tries…"
                    sleep $tries
                    if diskutil unmountDisk force "$mountvolume"; then
                        echo "IED:MSG:Forcefully unmounted '$mountvolume'"
                        result="success"
                        break
                    fi
                else
                    echo "IED:MSG:'$mountvolume' disappeared"
                    hdiutil info
                fi
            done
        else
            echo "IED:MSG:Unmounted '$mountvolume'"
            result="success"
        fi
        if [[ "$result" != "success" ]]; then
            echo "IED:MSG:Unmounting '$mountvolume' failed, giving up!"
        fi
    fi
}

eject_dmg() {
    local mountdev="$1"
    local result="failure"
    if [[ -e "$mountdev" ]]; then
        if ! hdiutil eject -verbose "$mountdev"; then
            for tries in {1..10}; do
                if [[ -e "$mountdev" ]]; then
                    echo "IED:MSG:Ejecting '$mountdev' failed, force attempt $tries…"
                    sleep $tries
                    if hdiutil eject -verbose "$mountdev" -force; then
                        echo "IED:MSG:Forcefully ejected '$mountdev'"
                        result="success"
                        break
                    fi
                else
                    echo "IED:MSG:'$mountdev' disappeared"
                    hdiutil info
                fi
            done
        else
            echo "IED:MSG:Ejected '$mountdev'"
            result="success"
        fi
        if [[ "$result" != "success" ]]; then
            echo "IED:MSG:Ejecting '$mountdev' failed, giving up!"
        fi
    fi
}

declare -a dmgmounts
unmount_dmgs() {
    for mountdev in "${dmgmounts[@]}"; do
        echo "IED:MSG:Ejecting '$mountdev'"
        eject_dmg "$mountdev"
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

if [[ $# -lt 5 ]]; then
    echo "IED:FAILURE:Usage: $(basename "$0") user group fstype output.dmg volname size OSInstall.mpkg [package...]"
    exit 100
fi
user="$1"
group="$2"
fstype="$3"
compresseddmg="$4"
volname="$5"
size="$6"
template="$7"
if [[ "$8" == *.dmg ]]; then
    sysimg="$8"
    shift 8
else
    shift 7
fi

# Get a work directory and check free space.
tempdir=$(mktemp -d "${TMPDIR:-/tmp/}installesdtodmg.XXXXXXXX")
tempdirs+=("$tempdir")
freespace=$(df -g "$tempdir" | tail -1 | awk '{print $4}')
if [[ "$freespace" -lt 15 ]]; then
    echo "IED:FAILURE:Less than 15 GB free disk space, aborting"
    exit 100
fi


# Keep track of version and build numbers before and after installing updates.
read_nvb() {
    local root="$1"
    if [[ "$root" == "/" ]]; then
        root=""
    fi
    local path="$root/System/Library/CoreServices/SystemVersion.plist"
    if [[ -f "$path" ]]; then
        name=$(/usr/libexec/PlistBuddy -c "print :ProductName" "$path")
        version=$(/usr/libexec/PlistBuddy -c "print :ProductUserVisibleVersion" "$path")
        build=$(/usr/libexec/PlistBuddy -c "print :ProductBuildVersion" "$path")
        echo "$name/$version/$build"
    fi
}

start_nvb=""


# Create and mount a sparse image.
echo "IED:PHASE:sparseimage"
if [[ -z "$sysimg" ]]; then
    echo "IED:MSG:Creating disk image with $fstype"
    sparsedmg="$tempdir/os.sparseimage"
    if ! hdiutil create -size "${size}g" -type SPARSE -fs "$fstype" -volname "$volname" -uid 0 -gid 80 -mode 1775 "$sparsedmg"; then
        echo "IED:FAILURE:Failed to create disk image for install"
        exit 101
    fi
    mountoutput=$(hdiutil attach -nobrowse -noautoopen -noverify -owners on "$sparsedmg")
    declare -i result=$?
    if [[ $result -ne 0 ]]; then
        echo "IED:FAILURE:Failed to mount disk image for install, return code $result"
        exit 101
    fi
    sparsemount=$(egrep '/Volumes/' <<< "$mountoutput" | head -1 | cut -f3)
    dmgmounts+=( $(egrep 'Apple_(H|AP)FS' <<< "$mountoutput" | awk '{print $1}') )
else
    echo "IED:MSG:Creating shadow file"
    
    shadowfile="$tempdir/autodmg.shadow"
    shadowoutput=$(hdiutil attach -shadow "$shadowfile" -nobrowse -noautoopen -noverify -owners on "$sysimg")
    declare -i result=$?
    if [[ $result -ne 0 ]]; then
        echo "IED:FAILURE:Failed to create shadow image for install, return code $result"
        exit 101
    fi
    targetdev=$(echo "$shadowoutput" | egrep '/Volumes/' | head -1 | awk '{print $1}')
    echo "IED:MSG:Renaming $targetdev to $volname"
    if ! diskutil rename "$targetdev" "$volname"; then
        echo "IED:FAILURE:Failed to rename install volume"
        exit 101
    fi
    sparsemount=$(egrep '/Volumes/' <<< "$shadowoutput" | head -1 | cut -f3)
    dmgmounts+=( $(egrep 'Apple_(H|AP)FS' <<< "$shadowoutput" | awk '{print $1}') )
    # If we're using a system image as the source, read the version and build
    # numbers before the first install.
    start_nvb=$(read_nvb "$sparsemount")
fi


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
            name="$(basename "$package")"
            if [[ "$name" == "OSInstall.mpkg" ]] || [[ "$name" == "InstallInfo.plist" ]]; then
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
    if [[ -z "$start_nvb" ]]; then
        start_nvb=$(read_nvb "$sparsemount")
    fi
done
if [[ $TESTING == "yes" ]]; then
    start_nvb="Mac OS X/9.0/53X248"
    end_nvb="macOS/10.64.1/64X738"
else
    end_nvb=$(read_nvb "$sparsemount")
fi
# Stop watching /var/log/install.log.
echo "IED:WATCHLOG:STOP"

# Copy template.
mkdir -p "$sparsemount/private/var/log"
rm -f "$sparsemount/private/var/log"/*.adtmpl
cp "$template" "$sparsemount/private/var/log"

# Finalize image.
echo "IED:PHASE:asr"

# Eject the dmgs.
echo "IED:MSG:Unmounting volume"
unmount_volume "$sparsemount"
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


# Report result.
echo "IED:SUCCESS:OUTPUT_PATH='$compresseddmg'"
name=$(echo "$end_nvb" | cut -d/ -f1)
version=$(echo "$end_nvb" | cut -d/ -f2)
build=$(echo "$end_nvb" | cut -d/ -f3)
echo "IED:SUCCESS:OUTPUT_OSNAME='$name'"
echo "IED:SUCCESS:OUTPUT_OSVERSION='$version'"
echo "IED:SUCCESS:OUTPUT_OSBUILD='$build'"
if [[ "$start_nvb" != "$end_nvb" ]]; then
    echo "IED:SUCCESS:Notice: OS version changed from $(echo $start_nvb | tr "/" " ") to $(echo $end_nvb | tr "/" " ")"
fi

exit 0
