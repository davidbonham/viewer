### Camera Image Viewer

This python script monitors a "hot folder" - that is, a folder into which
a remote tool, typically a tethered camera, is downloading JPEG images. 
Each  time a new image appears, it is displayed.

The tool also allows you to navigate through the existing images and display
them in a slide show.

If the script encounters a JPEG image it cannot load, perhaps because it
has been incompletely transferred or is corrupt, the image path is remembered
and will not be displayed again during navigation. (The 'x' key can be used
to clear this list of broken images if required.)

#### Command Line Usage

The minimum requirement is the location of the hot folder:

```bash
$ python3 viewer.py /path/to/hot/folder
```

but the following options can be added:

``--width WIDTH``

Specify the maximum displayed image width (in pixels) while preserving the
aspect ratio of the image. If not specified, the whole width of the screen 
will be used.

``--width HEIGHT``

Specify the maximum displayed image height (in pixels) while preserving the
aspect ratio of the image. If not specified, the whole height of the screen 
will be used.

``--bare``

Don't display the application window fram and title bar.

``--bell``

Sound the default system sound each time a new image is spotted in the 
hot folder

``--sort``

When navigating through a folder of existing images or performing a slide
show, sort them intp alphabetical order for display.

``--debug``

Provide some helpful information about actions being processed.

#### Key Bindings

Key(s)          | Action
--------------- | :-----
\<esc\>, q, Q   | Quit the application and return to the command line  
\<left\>, p, P  | Display the previous image, wrapping to the last 
\<right\>, n, N | Display the next image, wrapping to the first
\<home\>, h, H  | Display the first image
\<end\>         | Display the last image
\<space\>       | Toggle the slideshow performance on or off
+               | Double the speed of the slideshow and advance 
-               | Halve the speed of the slideshow and advance
c               | Toggle the centring of the image in the window
e               | Toggle the display of selected EXIF information
x               | Clear the list of images skipped because they appear corrupt


#### Dependencies

The script requires ``tkinter``, the python interface to Tcl/Tk and ``Pillow``,
the fork of PIL, the python image library.

    The Python Imaging Library (PIL) is:
    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh

    Pillow is the friendly PIL fork. It is:
    Copyright © 2010-2022 by Alex Clark and contributors

