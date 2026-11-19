"""Shared, approved alpha-only lower-bust envelope for PAL and JP CB art."""
from PIL import Image

def fade_portrait_rgba(image, *, native_rows=14, source_scale=4):
 """Return a new RGBA image; every source RGB channel remains unchanged.

 The final native_rows * source_scale raster rows contain a continuous
 envelope: .6*(1-t)+.4*(1-3*t*t+2*t*t*t), t=0..1 inclusive.
 It must be applied exactly once to the approved master, before reductions.
 """
 if image.mode!='RGBA':raise ValueError('The approved portrait must be RGBA')
 if type(native_rows)is not int or type(source_scale)is not int or native_rows<1 or source_scale<1:
  raise ValueError('Positive integer fade dimensions required')
 count=native_rows*source_scale
 if count<2 or count>image.height:raise ValueError('Fade must fit the source portrait')
 pixels=bytearray(image.tobytes());first=image.height-count
 for y in range(first,image.height):
  t=(y-first)/(count-1);envelope=.6*(1-t)+.4*(1-3*t*t+2*t*t*t)
  for x in range(image.width):
   at=(y*image.width+x)*4+3;pixels[at]=round(pixels[at]*envelope)
 return Image.frombytes('RGBA',image.size,bytes(pixels))
