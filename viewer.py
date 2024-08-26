import argparse
import csv
import datetime
import fractions
import os
import random
import statistics
import sys
import textwrap
import tkinter
from tkinter import font as tkFont
import tkinter.simpledialog
from typing import List

import PIL
from PIL import Image, ImageTk, ExifTags, ImageOps

# The Python Imaging Library (PIL) is
#
#    Copyright © 1997-2011 by Secret Labs AB
#    Copyright © 1995-2011 by Fredrik Lundh
#
# Pillow is the friendly PIL fork. It is
#
#    Copyright © 2010-2022 by Alex Clark and contributors

BGCOLOUR='#404040'

debugging = False
def debug(record):
    if debugging:
        print(record)


def treewalk(rootpath: str, wanted_types: List[str]) -> List[str]:
    def wanted(p: str):
        return any([p.endswith(suffix) for suffix in wanted_types])

    result: List[str] = []
    for root, dirs, files in os.walk(rootpath):
        wanted_files: List[str] = [file for file in files if wanted(file)]
        wanted_paths: List[str] = [os.path.join(root, file) for file in wanted_files]
        result.extend(wanted_paths)

    return result


class Viewer():

    def __init__(self, master, width=None, height=None, bare=False, bell=False, sort=False, randomise=False, treewalk=False, filter=None, path=None):

        self.image_index = None      # Index of the current image
        self.images = []             # The paths of images we know about
        self.skiplist = []           # Corrupt or missing images

        self.master = master
        self.rescan = False          # Updater is to start from scratch

        self.slideshow = False                      # Is the slideshow active?
        self.slideshow_ticks = 40                   # Ticks per image 40=10s
        self.slideshow_next = self.slideshow_ticks  # Ticks left for this image

        self.show_histogram = False  # Don't display the histogram yet
        self.bell = bell             # Don't ring the bell when new images appear
        self.centre_image = False    # Don't centre the image
        self.sort_on_load = sort     # Sort images on loading
        self.randomise_on_load = randomise     # Shuffle images on loading
        self.update = True           # Update current image when one arrives
        self.info = False            # Don't display info from Exif and current status
        self.path = path
        self.load_metadata()
        self.filter = filter
        self.treewalk = treewalk

        # Remove window manager decoration and processing of 'X' button
        # closing processing &c
        if bare:
            self.master.attributes('-fullscreen', True)


        # Set ourselves up as a full screen window unless the caller
        # overrides
        self.main_w = width if width else master.winfo_screenwidth()
        self.main_h = height if height else master.winfo_screenheight()
        master.geometry("%dx%d+0+0" % (self.main_w, self.main_h))

        master.title('Image Viewer')
        master.configure(bg=BGCOLOUR)

        master.focus_set()
        self.multibind(master, ["<Escape>", 'q', 'Q'], self.on_escape)
        self.multibind(master, ["<Left>", 'p', 'P'], self.on_left)
        self.multibind(master, ['<Right>', 'n', 'N'], self.on_right)
        self.multibind(master, ['<Home>', 'h', 'H'], self.on_home)
        self.multibind(master, ['<End>', 'e', 'E'], self.on_end)
        master.bind('<space>', self.on_space)
        master.bind('+', self.on_plus)
        master.bind('-', self.on_minus)
        master.bind('c', self.on_centre)
        master.bind('e', self.on_histogram)
        master.bind('t', self.on_text)
        master.bind('u', self.on_update)
        master.bind('x', self.on_clearskip)
        master.bind('i', self.on_info)

        for rating in range(10):
            master.bind(str(rating), self.on_rating)
        for filter in '!".$%^&*()':
            master.bind(filter, self.on_filter)


        # We'll display our image in a label widget with no border
        self.image_widget = tkinter.Canvas(master, width=self.main_w, height=self.main_h)
        self.image_widget.pack()
        self.image_widget.configure(bd=0, background=BGCOLOUR)
        self.canvas_image = None
        debug('Viewer constructed')

    def goto_image(self, index, delta=1):
        '''
        Go to the image in the list, wrapping at the ends. If there are no
        images, do nothing
        '''

        if index != None:
            self.image_index = index % len(self.images)

            if self.filter:
                for _ in range(len(self.images)):
                    image_name = os.path.basename(self.images[self.image_index])
                    in_metadata = image_name in self.metadata
                    rating = '0' if not in_metadata else self.metadata[image_name]['rating']
                    if rating >= self.filter:
                        break
                    debug(f'skip image {self.image_index} in metadata {in_metadata} rating {rating}')
                    self.image_index = (self.image_index+delta) % len(self.images)

            self.load_image()

    def on_clearskip(self, _):
        '''
        The next scan will reinspect files no longer on the skip list
        '''
        debug('on_clearskip')
        self.skiplist = []

    def on_centre(self, _):
        '''
        Toggle centring of images
        '''
        debug('on_centre')
        self.centre_image = not self.centre_image
        self.load_image()

    def on_escape(self, event):
        '''Quit the application'''
        debug('escape')
        event.widget.withdraw()
        event.widget.quit()

    def on_home(self, _):
        '''Go to the first image in the list'''
        debug('home')
        self.goto_image(0)

    def on_end(self, _):
        '''Go to the final image in the list'''
        debug('end')
        self.goto_image(len(self.images) - 1)


    def on_left(self, _):
        '''Go to the previous image, wrapping at the start'''
        debug('left')
        self.goto_image(self.image_index - 1, delta=-1)

    def on_right(self, _):
        '''Go to the next image, wrapping at the end'''
        debug('right')
        self.goto_image(self.image_index + 1)

    def on_space(self, _):
        '''Toggle slideshow'''
        self.slideshow = not self.slideshow
        debug(f'space {self.slideshow}')

    def on_plus(self, _):
        '''Double speed of slideshow and step on to the next.'''
        if self.slideshow_ticks >= 2:
            self.slideshow_ticks //= 2
        debug(f'plus {self.slideshow_ticks}')
        self.slideshow_next = 1

    def on_minus(self, _):
        '''Halve the speed of the slideshow'''
        self.slideshow_ticks *= 2
        debug(f'minus {self.slideshow_ticks}')

    def on_rating(self, info):
        current_image_name = os.path.basename(self.images[self.image_index])
        if current_image_name not in self.metadata:
            self.metadata[current_image_name] = {'notes': ''}
        self.metadata[current_image_name]['rating'] = info.char

        # If the EDIT data is visible, toggle to redraw it all
        if self.show_histogram:
            self.on_histogram(None)
            self.on_histogram(None)

        # And make sure all is safe
        self.save_metadata()

    def on_filter(self, info):
        self.filter = chr(ord('0') + ')!".$%^&*('.find(info.char))
        debug(f'on_rating \'{info.char}\' sets rating filter \'{self.filter}\'')

    def on_update(self,_):
        self.update = not self.update
        debug(f'on_update sets updating {self.update}')
        self.updater()

    def on_info(self, _):
        self.info = not self.info
        debug(f'on_info sets info display {self.info}')
        self.updater()

    def on_text(self, _):

        # Get the current notes as the inital setting
        current_image_name = os.path.basename(self.images[self.image_index])
        notes = self.metadata.get(current_image_name, {'notes': ''})['notes']
        reply = tkinter.simpledialog.askstring('Notes', '', initialvalue=notes)

        # If the user replied, update the notes
        if reply:
            if current_image_name not in self.metadata:
                self.metadata[current_image_name] = {'rating': '0'}
            self.metadata[current_image_name]['notes'] = reply

            # If the EDIT data is visible, toggle to redraw it all
            if self.show_histogram:
                self.on_histogram(None)
                self.on_histogram(None)

            # And make sure all is safe
            self.save_metadata()

    def multibind(self, widget, events, handler):
        '''Bind the handler to each event in the list'''
        for item in events:
            widget.bind(item, handler)

    def on_histogram(self, _):
        '''Toggle drawing of histogram'''
        self.show_histogram = not self.show_histogram
        debug(f'histogram {self.show_histogram}')
        if not self.show_histogram:
            # Undraw the histogram by deleting it from the canvas display file
            self.image_widget.delete('exposure')
        else:
            # Draw the histogram by redoing it all, which is a little slow
            self.goto_image(self.image_index)

    def get_exif_info(self, pil_image):
        '''
        Return a dictionary containing all the interesting information
        where the keys are the user-friendly labels. If there is no
        EXIF info of interest, the dictionary will be empty.
        '''

        # This provides baseline information only
        exif_data = pil_image.getexif()
        result = {ExifTags.TAGS[key]: value for key, value in exif_data.items() if key in ExifTags.TAGS and ExifTags.TAGS[key] in ('Model',)}

        # The interesting stuff is in the Private TIFF tag IFD with the tag ExifIFD=0x8769
        ifd_data = exif_data.get_ifd(0x8769)

        # Create a subset of the TAGS dictionary containing the items we're
        # interested in
        public_name = {
            'ExposureBiasValue': 'EV',
            'ExposureTime': 'Exposure Time',
            'MeteringMode': 'Metering Mode',
            'FocalLength' : 'Focal Length',
            'FNumber'     : 'Aperture',
            'ExposureProgram': 'Program',
            'ISOSpeedRatings': 'ISO',
            'ExposureMode': 'Exposure Mode',
            'LensModel': 'Lens',
        }

        wanted_tags = {key: public_name[name] for key, name in ExifTags.TAGS.items() if name in (
            'ExposureBiasValue',
            'ExposureTime',
            'MeteringMode',
            'FocalLength',
            'FNumber',
            'ExposureProgram',
            'ISOSpeedRatings',
            'ExposureMode',
            'LensModel',
        )}

        # Add wanted items that are not in the Exif tags dictionary
        wanted_tags[37510] = 'User Comment'

        # For every tag in the ifd data which is in our TAGS dictionary,
        # place it's name and value in our results
        ifd_tags = {wanted_tags[tag]: value for tag, value in ifd_data.items() if tag in wanted_tags}

        result.update(ifd_tags)

        # Fix up some values to make them more familiar
        if 'Exposure Time' in result:
            rational = result['Exposure Time']
            if rational < 1:
                # Not necessarily in lowest terms
                # Not necessarily in lowest terms
                fraction = fractions.Fraction(rational.numerator, rational.denominator)
                result['Exposure Time'] = f'{fraction.numerator}/{fraction.denominator} sec'
            else:
                result['Exposure Time'] = f'{rational} sec'

        if 'EV' in result:
            rational = result['EV']
            sign = '+' if rational >= 0 else '-'
            if sign == '-': rational = -rational
            whole = int(rational)
            fraction = rational - whole
            if fraction.numerator != 0:
                result['EV'] = f'{sign}{whole if whole != 0 else ""} {fraction.numerator}/{fraction.denominator}'
            else:
                result['EV'] = f'{sign}{whole}'

        if 'Focal Length' in result:
            result['Focal Length'] = f'{result["Focal Length"]}mm'

        if 'Aperture' in result:
            aperture = f'f/{result["Aperture"]}'
            if aperture.endswith('.0'): aperture = aperture[:-2]
            result['Aperture'] = aperture

        if 'ISO' in result:
            result['ISO'] = f'{result["ISO"]}'

        if 'Metering Mode' in result:
            result['Metering Mode'] = {
                0 : 'Unknown',
                1 : 'Average',
                2 : 'CenterWeightedAverage',
                3 : 'Spot',
                4 : 'MultiSpot',
                5 : 'Pattern',
                6 : 'Partial',
                255 : 'other',
            }.get(result['Metering Mode'], 'Undefined')

        if 'Program' in result:
            result['Program'] = {
            0 : 'Not defined',
                1 : 'Manual',
                2 : 'Normal',
                3 : 'Aperture',
                4 : 'Shutter',
                5 : 'Creative',
                6 : 'Action',
                7 : 'Portrait',
                8 : 'Landscape'

            }.get(result['Program'], 'Undefined')

        if 'Exposure Mode' in result:
            result['Exposure Mode'] = {
                0 : 'Auto',
                1 : 'Manual',
                2 : 'Auto bracket'
            }.get(result['Exposure Mode'], 'Undefined')

        # If there is a TIFF UserComment attribute (37510), decode it
        if 'User Comment' in result:
            raw_comment = result['User Comment']
            # The first eight bytes are the encoding. We expect this to be utf-16 at the moment or else we ignore it.
            # to vary depending on the tool that wrote it and they don't seem to write a BOM.
            encoding = raw_comment[:8]
            data = raw_comment[8:]
            debug(f'user comment detected with encoding {encoding}')
            if encoding == b'UNICODE\x00':
                # We need the endianness :
                utf16_order = 'utf-16be' if exif_data.endian == '>' else 'utf-16le'
                decoded_data = data.decode(utf16_order)
                result['User Comment'] = decoded_data
            else:
                # Assume this is ascii
                result['User Comment'] = data.decode('ascii')
        return result


    def draw_histogram(self, pil_image, image_path):
        '''Given a PIL image, render the histogram for it'''

        # We need a greyscale version which has 256 values
        mono = pil_image.convert('L')
        histogram = mono.histogram()

        # Fix the histogram size at 256 pixels wide (one per luminosity value)
        # and a third as high. and position it at the top right of the canvas
        # with a margin of 10 pixels above and to the right.
        NUMLEVELS = 256
        BINWIDTH = 1
        MAXH = 256 // 2
        MARGIN = 10
        origin_x = self.main_w - MARGIN - NUMLEVELS
        origin_y = 0 + MARGIN + MAXH

        # Allow for some smoothing of data by averaging adjacent samples
        if BINWIDTH > 1:
            # We need to reduce the histogram size
            for b in range(len(histogram) / BINWIDTH):
                bins = range(BINWIDTH*b, BINWIDTH*(b+1))
                bin_mean = sum([histogram[x] for x in bins]) / BINWIDTH
                for bin in bins:
                    histogram[bin] = bin_mean

        # Stop a few huge intensities dwarfing the others by clipping
        # at an intensity that exceeds 97.5% of the histogram values.
        # If the image is practially all black, the last quantile may
        # be very small or even zero - use 10 as a minimum.
        clip = max(10, statistics.quantiles(histogram, n=25)[-1])

        # We need to scale the brightness into the range 0..MAXH
        debug(f'histogram clip={clip} total={sum(histogram)}')
        scale = MAXH / clip
        polygon = [(origin_x + x, origin_y - scale*min(clip,histogram[x])) for x in range(NUMLEVELS)]

        # Delete the old histogram if there was one
        self.image_widget.delete('exposure')

        # Draw the new one and keep track of the canvas display file ids
        self.image_widget.create_rectangle(origin_x, origin_y, origin_x+NUMLEVELS, origin_y-MAXH, fill='#202020', outline='', tags='exposure')
        self.image_widget.create_polygon((origin_x, origin_y), *polygon, (origin_x+NUMLEVELS, origin_y), fill='white', tags='exposure')

        # Now add EXIF info if there is any. We cheat a bit here and add our own
        # rating and notes as EXIF tags
        exif_info = self.get_exif_info(pil_image)
        image_name = os.path.basename(image_path)
        metadata = self.metadata.get(image_name, {'rating': '0', 'notes': ''})
        rating = metadata['rating']
        notes = metadata['notes']
        if rating != '0':
            exif_info['Rating'] = rating
        if notes != '':
            exif_info['Notes'] = notes
        exif_info['Name'] = os.path.basename(image_path)
        exif_info['Time'] = f'{datetime.datetime.now():%H:%M:%S}'

        if len(exif_info) > 0:

            # Treat some items specially - mainly to keep the width down
            text = ''
            longest = 0
            if 'Model' in exif_info:
                text += exif_info['Model'] + '\n'
                longest = max (longest, len(exif_info['Model']))
                del exif_info['Model']
            if 'Lens' in exif_info:
                text += exif_info['Lens'] + '\n'
                longest = max(longest, len(exif_info['Lens']))
                del exif_info['Lens']
            if 'Aperture' in exif_info and 'Exposure Time' in exif_info and 'ISO' in exif_info:
                text += f'{exif_info["Exposure Time"]} at {exif_info["Aperture"]}, ISO {exif_info["ISO"]}\n'

            if 'User Comment' in exif_info:
                if self.info:
                    # The comment will be long so wrap it into multiple lines
                    comments = textwrap.wrap(exif_info['User Comment'], 60)
                    text += '\n'.join(comments)
                del exif_info['User Comment']


            text += '\n'

            # The width of the longest remaining label so we can pad them
            # to this width
            max_label_width = max([len(label) for label in exif_info], default=longest) + 1
            text += '\n'.join([f'{label+":":{max_label_width}} {value}' for label, value in exif_info.items()])
            text_id = self.image_widget.create_text(origin_x+256, origin_y+20, text=text, fill='white', anchor='ne', font=('Consolas', 10), tags='exposure')

            # In case the text overlaps the image and the image is the same
            # colour as the text, we'll get the extent of the text and draw
            # a grey rectangle behind it
            extent = self.image_widget.bbox(text_id)
            rect_id = self.image_widget.create_rectangle(*extent, fill=BGCOLOUR, outline=BGCOLOUR, tags='exposure')
            self.image_widget.tag_raise(text_id, rect_id)


    def load_image(self):
        '''Load the image with the current image index'''
        if self.image_index == None: return

        # Get PIL to load the image
        path = self.images[self.image_index]
        try:
            pil_image = Image.open(path, 'r')
            pil_image.load()
            ImageOps.exif_transpose(pil_image, in_place=True)

        except (PIL.UnidentifiedImageError, FileNotFoundError, OSError) as e:
            #if isinstance(e, FileNotFoundError):
                #print(f'image {path} missing - rescanning directory', file=sys.stderr)
                #self.rescan = True
            #else:
            #    print(f'unable to load image {path} - skipping', file=sys.stderr)
            print(f'warning: skipping {path} - {e}', file=sys.stderr)
            self.skiplist.append(path)
            del self.images[self.image_index]

            self.load_image()
            return


        imgWidth, imgHeight = pil_image.size
        self.master.title(f'Image Viewer - {imgWidth}x{imgHeight} - {path}')

        # Scale the image to fit the screen - the dimension that
        # needs scaling most gives us the scale factor to use.
        w_scale = imgWidth / self.main_w
        h_scale = imgHeight / self.main_h
        scale = max(w_scale, h_scale)
        new_size = (int(imgWidth/scale), int(imgHeight/scale))

        # This is the first operation on the file and so the point at which
        # a corrupt image will be detected
        pil_image = pil_image.resize(new_size)

        # We need to keep a reference to the photo image alive to
        # prevent it being garbage collected
        self.current_image = ImageTk.PhotoImage(pil_image)
        if self.canvas_image != None:
            self.image_widget.delete(self.canvas_image)
        if self.centre_image:
            self.canvas_image = self.image_widget.create_image(self.main_w/2, self.main_h/2, anchor='center', image=self.current_image)
        else:
            self.canvas_image = self.image_widget.create_image(0, 0, anchor='nw', image=self.current_image)

        debug(f'loaded {self.image_index}={self.images[self.image_index]}')

        if self.show_histogram:
            self.draw_histogram(pil_image, path)


    def updater(self):
        '''Called regularly to see if new images have appeared on disk'''

        if not self.update: return

        if self.rescan:
            debug('rescan')
            # We've been asked to rescan the directory - perhaps a file disappeared
            self.images = []
            self.image_index = None
            self.rescan = False

        # All of the files in the hot directory that end in .jpg
        if self.treewalk:
            paths = treewalk(self.path, ['.jpeg', '.jpg'])
        else:
            # Simple way to collect our images
            paths = [os.path.join(self.path, file) for file in os.listdir(self.path) if file.lower().endswith('.jpg') or file.lower().endswith('.jpeg')]

        # Images that have appeared since we last looked, ignoring the corrupt
        # ones we already know about
        new_images = [path for path in paths if path not in self.images and path not in self.skiplist and os.path.isfile(path)]

        if new_images != []:

            # There are new images so whereever we were, move
            # to the first new image and display it
            debug(f'saw {new_images}')
            random.shuffle(new_images)

            self.image_index = len(self.images)
            self.images.extend(new_images)
            if self.sort_on_load:
                self.images.sort()
            self.load_image()

            # Reset the slideshow
            self.slideshow = False
            self.slideshow_next = self.slideshow_ticks

            if self.bell:
                self.master.bell()

        if self.slideshow:
            self.slideshow_next -= 1
            if self.slideshow_next == 0:
                self.slideshow_next = self.slideshow_ticks
                self.on_right(None)

        '''We want to be called again'''
        self.master.after(250, self.updater)

    def load_metadata(self):
        '''
        The file 'metadata.csv' in the hot folder, if it exists, holds
        records with the format

        "filename", rating, "notes"

        Read it into a dictonary mapping filename to rating and notes and
        return it.
        '''
        self.metadata = {}
        metadata_db = os.path.join(self.path, 'metadata.csv')
        if os.path.isfile(metadata_db):
            with open(metadata_db, 'r') as db:
                rows = csv.reader(db)

                for image, rating, notes in rows:
                    # To allow us to relocate the date, only use the
                    # basename until we support subtrees
                    image = os.path.basename(image)
                    self.metadata[image]= {'rating': rating, 'notes': notes}

    def save_metadata(self):
        '''
        Save the updated ratings if there are any.
        '''
        if len(self.metadata) > 0:
            metadata_db = os.path.join(self.path, 'metadata.csv')
            with open(metadata_db, 'w', newline='') as db:
                for image in self.metadata.keys():

                    # Only use base name so we can relocate the data
                    image = os.path.basename(image)
                    # We put the rating first in case the notes contains spaces
                    writer = csv.writer(db)
                    writer.writerow([image, self.metadata[image]['rating'], self.metadata[image]['notes']])

import sys

if __name__ == '__main__':

    epilog_text = '''

navigation keys:
  <Escape>, q, Q   Quit
  <Left>, p, P     Go to previous image
  <Right>, n, N    Go to next image
  <Home>, h, H     Go to the first image in the folder
  <End>, e, E      Go to the last image in the folder
  <Space>          Toggle the slideshow
  +                Double the speed of the slideshow
  -                Halve the speed of the slideshow
  c                Toggle centring of images
  e                Toggle display of the histogram and EXIF info
  x                Clear the list of images being skipped because we failed to load them
  u                Toggle automatic updating
  0,1,...9         Rate the current image
'''

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description  = 'Display images as they appear in a hot folder',
        epilog = epilog_text
    )
    parser.add_argument('--width', type=int, help='Width of app window')
    parser.add_argument('--height', type=int, help='Height of app window')
    parser.add_argument('--bare', action='store_true', help='Disable window manager decoration')
    parser.add_argument('--bell', action='store_true', help='Ring the bell when new images appear')
    parser.add_argument('--sort', action='store_true', help='Sort images into alphabetical order')
    parser.add_argument('--debug', action='store_true', help='Print debug info to standard output')
    parser.add_argument('--randomise', action='store_true', help='Randomise the initial order')
    parser.add_argument('--treewalk', action='store_true', help='Include subdirectories in the scan')
    parser.add_argument('--filter', type=str, help='Set the minimum rating to display')

    parser.add_argument('directory', help='Path to hot folder')
    args = parser.parse_args()

    debugging = args.debug
    tk = tkinter.Tk()

    app = Viewer(master=tk, width=args.width, height=args.height,
                 bare=args.bare, bell=args.bell,
                 sort=args.sort, randomise=args.randomise, treewalk=args.treewalk,
                 filter=args.filter,
                 path=args.directory)
    tk.after(10, app.updater)
    tk.mainloop()


