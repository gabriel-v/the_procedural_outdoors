#!/bin/bash -ex

DELAY=50
FRAMERATE=2

echo "MAKING GIFS....."
mkdir -p output/gif
mkdir -p output/vid


for z in 1 2 3; do
	for i in $(ls output/pics/rgba_* | grep rgba_ | cut -d_ -f2 | cut -d. -f1); do
		montage -font DejaVu-Sans-Mono -label %t -tile 4x2 -geometry 333x333 output/pics/*_$i.png output/pics/concat_$i.png
	done
done


for gif in rgba segmentation depth backward forward normal object concat; do
	convert -delay $DELAY -loop 0 output/pics/${gif}*.png output/gif/${gif}.gif
done

for gif in rgba segmentation depth backward forward normal object concat; do
	ffmpeg -y -r $FRAMERATE \
		-pattern_type glob -i 'output/pics/'$gif'*.png' \
		-c:v libx264 -vf "fps=25,format=yuv420p"  \
		output/vid/$gif.mp4
done
echo "DONE MAKING GIFS."
