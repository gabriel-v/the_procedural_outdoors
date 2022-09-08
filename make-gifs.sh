#!/bin/bash -e

DELAY=8
FRAMERATE=12

echo "start montage, gif, video....."
mkdir -p output/gif
mkdir -p output/vid


ls output/pics/rgba_* | grep rgba_ | cut -d_ -f2 | cut -d. -f1 | \
	xargs -I{} -n1 -P8 --verbose \
	montage -font DejaVu-Sans-Mono -label %t -tile 2x3 -geometry 480x270 \
	output/pics/*_{}.png output/pics/concat_{}.png

echo "montage done"

echo "making gifs..."
for gif in rgba segmentation depth normal concat; do
	convert -delay $DELAY -loop 0 output/pics/${gif}*.png output/gif/${gif}.gif &
done
wait
echo "gif done"

for gif in rgba segmentation depth normal concat; do
	ffmpeg -y -r $FRAMERATE \
		-pattern_type glob -i 'output/pics/'$gif'*.png' \
		-c:v libx264 -vf "fps=24,format=yuv420p"  \
		output/vid/$gif.mp4 &
done
wait
echo "vids done"

cp output/gif/concat.gif output/concat.gif
cp output/vid/concat.mp4 output/concat.mp4
