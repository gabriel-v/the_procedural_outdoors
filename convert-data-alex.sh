#!/bin/bash -ex

rm -rf ./output/convert-alex/* || true

mkdir -p output/convert-alex/frames
mkdir -p output/convert-alex/ground_truths


i=894
for f in output/pics/rgba_*.png; do
  cp $f output/convert-alex/frames/$i.png
  if [ $(($i % 2)) == 0 ]; then
    convert output/convert-alex/frames/$i.png -flop output/convert-alex/frames/$i-tmp.png
    mv output/convert-alex/frames/$i-tmp.png output/convert-alex/frames/$i.png
  fi

  convert output/convert-alex/frames/$i.png -auto-gamma output/convert-alex/frames/$i-tmp.png
  mv output/convert-alex/frames/$i-tmp.png output/convert-alex/frames/$i.png
  i=$((i+1))
done

i=894
for f in output/pics/rails_segmentation_*.png; do
  convert -monochrome $f output/convert-alex/ground_truths/$i.png
  if [ $(($i % 2)) == 0 ]; then
    convert output/convert-alex/ground_truths/$i.png -flop output/convert-alex/ground_truths/$i-tmp.png
    mv output/convert-alex/ground_truths/$i-tmp.png output/convert-alex/ground_truths/$i.png
  fi
  i=$((i+1))
done
