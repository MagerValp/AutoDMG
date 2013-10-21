#!/bin/bash


sips -Z 512 icon_512x512@2x.png --out icon_512x512.png
sips -Z 512 icon_512x512@2x.png --out icon_256x256@2x.png
sips -Z 256 icon_512x512@2x.png --out icon_256x256.png
sips -Z 256 icon_512x512@2x.png --out icon_128x128@2x.png
sips -Z 128 icon_512x512@2x.png --out icon_128x128.png

sips -Z 64 icon_512x512@2x.png --out icon_32x32@2x.png
sips -Z 32 icon_512x512@2x.png --out icon_32x32.png
sips -Z 32 icon_512x512@2x.png --out icon_16x16@2x.png
sips -Z 16 icon_512x512@2x.png --out icon_16x16.png
