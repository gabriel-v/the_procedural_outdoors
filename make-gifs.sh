#!/bin/bash -e

DELAY=4
FRAMERATE=24

echo "start montage, gif, video....."
mkdir -p output/gif
mkdir -p output/vid


for z in 1 2; do
	echo "montage iter $z ..."
	ls output/pics/rgba_* | grep rgba_ | cut -d_ -f2 | cut -d. -f1 | \
		xargs -I{} -n1 -P8 --verbose \
		montage -font DejaVu-Sans-Mono -label %t -tile 4x2 -geometry 333x333 \
		output/pics/*_{}.png output/pics/concat_{}.png

	wait
done
echo "montage done"

echo "making gifs..."
for gif in rgba segmentation depth backward forward normal object concat; do
	convert -delay $DELAY -loop 0 output/pics/${gif}*.png output/gif/${gif}.gif &
done
wait
echo "gif done"

for gif in rgba segmentation depth backward forward normal object concat; do
	ffmpeg -y -r $FRAMERATE \
		-pattern_type glob -i 'output/pics/'$gif'*.png' \
		-c:v libx264 -vf "fps=24,format=yuv420p"  \
		output/vid/$gif.mp4 &
done
wait
echo "vids done"

cp output/gif/concat.gif output/concat.gif
cp output/vid/concat.mp4 output/concat.mp4
