#! /bin/bash

# refresh derived resources
inkscape place_footprints_dark.svg -w 24 -h 24 -o place_footprints_dark.png
inkscape place_footprints_light.svg -w 24 -h 24 -o place_footprints_light.png
inkscape place_footprints_light.svg -w 64 -h 64 -o place_footprints.png

# refresh the GUI design
~/WxFormBuilder/bin/wxformbuilder -g initial_dialog_GUI.fbp
~/WxFormBuilder/bin/wxformbuilder -g place_by_reference_GUI.fbp
~/WxFormBuilder/bin/wxformbuilder -g place_by_sheet_GUI.fbp

# grab version and parse it into metadata.json
cp metadata_source.json metadata_package.json
version=`cat version.txt`
sed -i -e "s/VERSION/$version/g" metadata_package.json

# cut the download, sha and size fields
sed -i '/download_url/d' metadata_package.json
sed -i '/download_size/d' metadata_package.json
sed -i '/install_size/d' metadata_package.json
sed -i '/download_sha256/d' metadata_package.json

# prepare the package
mkdir plugins
cp place_footprints_dark.png plugins
cp place_footprints_light.png plugins
cp __init__.py plugins
cp action_place_footprints.py plugins
cp initial_dialog_GUI.py plugins
cp place_by_reference_GUI.py plugins
cp place_by_sheet_GUI.py plugins
cp archive_3d_models.py plugins
cp place_footprints.py plugins
cp version.txt plugins
mkdir resources
cp place_footprints.png resources/icon.png
cp metadata_package.json metadata.json

zip -r PlaceFootprints-$version-pcm.zip plugins resources metadata.json

# clean up
rm -r resources
rm -r plugins
rm metadata.json

# get the sha, size and fill them in the metadata
cp metadata_source.json metadata.json
version=`cat version.txt`
sed -i -e "s/VERSION/$version/g" metadata.json
zipsha=`sha256sum PlaceFootprints-$version-pcm.zip | xargs | cut -d' ' -f1`
sed -i -e "s/SHA256/$zipsha/g" metadata.json
unzipsize=`unzip -l PlaceFootprints-$version-pcm.zip | tail -1 | xargs | cut -d' ' -f1`
sed -i -e "s/INSTALL_SIZE/$unzipsize/g" metadata.json
dlsize=`ls -al PlaceFootprints-$version-pcm.zip | tail -1 | xargs | cut -d' ' -f5`
sed -i -e "s/DOWNLOAD_SIZE/$dlsize/g" metadata.json
