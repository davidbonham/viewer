import argparse 
import os
import statistics
import sys
import tkinter
import PIL
from PIL import Image, ImageTk, ExifTags, TiffTags

debugging = False
def debug(record):
    if debugging:
        print(record)


class Viewer():

    def __init__(self, master, width=None, height=None, bare=False, bell=False):

        self.image_index = None      # Index of the current image
        self.images = []             # The paths of images we know about
        self.master = master
        self.rescan = False          # Updater is to start from scratch

        self.slideshow = False                      # Is the slideshow active?
        self.slideshow_ticks = 40                   # Ticks per image 40=10s
        self.slideshow_next = self.slideshow_ticks  # Ticks left for this image

        self.show_histogram = False  # Don't display the histogram yet
        self.bell = bell             # Don't ring the bell when new images appear

        #Remove window manager decoration and processing of 'X' button 
        #closing processing &c
        if bare:
            self.master.attributes('-fullscreen', True)
            #self.master.overrideredirect(1)

 
        # Set ourselves up as a full screen window unless the caller
        # overrides
        self.screen_w = width if width else master.winfo_screenwidth()
        self.screen_h = height if height else master.winfo_screenheight()
        master.geometry("%dx%d+0+0" % (self.screen_w, self.screen_h))

        master.title('Image Viewer')
        master.configure(bg='#202020')

        master.focus_set()    
        self.multibind(master, ["<Escape>", 'q', 'Q'], self.on_escape)
        self.multibind(master, ["<Left>", 'p', 'P'], self.on_left)
        self.multibind(master, ['<Right>', 'n', 'N'], self.on_right)
        self.multibind(master, ['<Home>', 'h', 'H'], self.on_home)
        self.multibind(master, ['<End>', 'e', 'E'], self.on_end)
        master.bind('<space>', self.on_space)
        master.bind('+', self.on_plus)
        master.bind('-', self.on_minus)
        master.bind('e', self.on_histogram)

        # We'll display our image in a label widget with no border
        self.image_widget = tkinter.Canvas(master, width=self.screen_w, height=self.screen_h)
        self.image_widget.pack()
        self.image_widget.configure(bd=0, background='#808080')
        self.canvas_image = None
        debug('Viewer constructed')


    def goto_image(self, index):
        '''Go to the image in the list, wrapping at the ends'''
        self.image_index = index % len(self.images)
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
        self.goto_image(self.image_index - 1)

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

        # This provides baseline information only
        exif_data = pil_image.getexif()
        result = {ExifTags.TAGS[key]: value for key, value in exif_data.items() if ExifTags.TAGS[key] in ('Model',)}

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
            #'WhiteBalance',
            #'RecommendedExposureIndex',
            #'LensSpecification',
            'LensModel': 'Lens'

        }
        wanted_tags = {key: public_name[name] for key, name in ExifTags.TAGS.items() if name in (
            #'ApertureValue',
            'ExposureBiasValue',
            'ExposureTime',
            'MeteringMode',
            'FocalLength',
            'FNumber',
            'ExposureProgram',
            'ISOSpeedRatings',
            'ExposureMode',
            #'WhiteBalance',
            #'RecommendedExposureIndex',
            #'LensSpecification',
            'LensModel',
        )}

        # For every tag in the ifd data which is in our TAGS dictionary,
        # place it's name and value in our results
        ifd_tags = {wanted_tags[tag]: value for tag, value in ifd_data.items() if tag in wanted_tags}

        result.update(ifd_tags)

        # Fix up some values to make them more familiar
        if 'Exposure Time' in result:
            rational = result['Exposure Time']
            if rational < 1:
                result['Exposure Time'] = f'{rational.numerator}/{rational.denominator} sec' 
            else:
                result['Exposure Time'] = f'{rational} sec'  

        if 'EV' in result:
            rational = result['EV']
            whole = int(rational)
            fraction = rational - whole
            sign = '+' if rational >= 0 else '-'
            if fraction.numerator != 0:
                result['EV'] = f'{sign}{whole if whole != 0 else ""} {fraction.numerator}/{fraction.denominator}'
            else:
                result['EV'] = f'{sign}{whole}'

        if 'Focal Length' in result:
            result['Focal Length'] = f'{result["Focal Length"]}mm'
        
        if 'Aperture' in result:
            result['Aperture'] = f'f/{result["Aperture"]}'
        
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
            }[result['Metering Mode']]
        
        if 'Program' in result:
            result['Program'] = {
            0 : 'Not defined',
                1 : 'Manual',
                2 : 'Normal program',
                3 : 'Aperture priority',
                4 : 'Shutter priority',
                5 : 'Creative program',
                6 : 'Action program',
                7 : 'Portrait mode',
                8 : 'Landscape mode'

            }[result['Program']]

        if 'Exposure Mode' in result:
            result['Exposure Mode'] = {
                0 : 'Auto',
                1 : 'Manual',
                2 : 'Auto bracket'
            }[result['Exposure Mode']]
        return result


    def draw_histogram(self, pil_image):
        '''Given a PIL image, render the histogram for it'''

        # We need a greyscale version which has 256 values
        mono = pil_image.convert('L')
        histogram = mono.histogram()

        # Fix the histogram size at 256 pixels wide (one per luminosity value)
        # and a third as high. and position it at the top right of the canvas
        # with a margin of 10 pixels above and to the right.
        BINWIDTH = 1
        MAXH = 256 // 3
        origin_x = self.screen_w - 10 - 256
        origin_y = 0 + 10 + MAXH
        
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
        polygon = [(origin_x + x, origin_y - scale*min(clip,histogram[x])) for x in range(256)]

        # Delete the old histogram if there was one
        self.image_widget.delete('exposure')
            
        # Draw the new one and keep track of the canvas display file ids    
        self.image_widget.create_rectangle(origin_x, origin_y, origin_x+256, origin_y-MAXH, fill='#202020', outline='', tags='exposure')
        self.image_widget.create_polygon((origin_x, origin_y), *polygon, (origin_x+255, origin_y), fill='white', tags='exposure')
        
        # Now add EXIF info if there is any
        exif_info = self.get_exif_info(pil_image)
        if len(exif_info) > 0:

            # Treat some items specially - mainly to keep the width down
            text = ''
            if 'Model' in exif_info:
                text += exif_info['Model'] + '\n'
                del exif_info['Model']
            if 'Lens' in exif_info:
                text += exif_info['Lens'] + '\n'
                del exif_info['Lens']
            text += '\n'

            # The width of the longest remianing label so we can pad them
            # to this width 
            max_label_width = max(len(label) for label in exif_info) + 1
            text += '\n'.join([f'{label+":":{max_label_width}} {value}' for label, value in exif_info.items()])
            text_id = self.image_widget.create_text(origin_x+256, origin_y+20, text=text, fill='white', anchor='ne', font=('Consolas', 10), tags='exposure')

            # In case the text overlaps the image and the image is the same
            # colour as the text, we'll get the extent of the text and draw
            # a grey rectangle behind it
            extent = self.image_widget.bbox(text_id)
            rect_id = self.image_widget.create_rectangle(*extent, fill='#808080', outline='#808080', tags='exposure')
            self.image_widget.tag_raise(text_id, rect_id)


    def load_image(self):
        '''Load the image with the current image index'''
        if self.image_index == None: return

        # Get PIL to load the image
        path = self.images[self.image_index]
        try:
            pil_image = Image.open(path, 'r')
        except (PIL.UnidentifiedImageError, FileNotFoundError) as e:
            if isinstance(e, FileNotFoundError):
                print(f'image {path} missing - rescanning directory', file=sys.stderr)
                self.rescan = True
            else:
                print(f'unable to load image {path} - skipping', file=sys.stderr)

            self.on_right(None)
            return

        exif_info = self.get_exif_info(pil_image)
        for name, value in exif_info.items():
            print(f'{name}: {value}')


        imgWidth, imgHeight = pil_image.size
        self.master.title(f'Image Viewer - {imgWidth}x{imgHeight} - {path}')

        # Scale the image to fit the screen - the dimension that
        # needs scaling most gives us the scale factor to use.
        w_scale = imgWidth / self.screen_w
        h_scale = imgHeight / self.screen_h
        scale = max(w_scale, h_scale)
        new_size = (int(imgWidth/scale), int(imgHeight/scale))

        pil_image = pil_image.resize(new_size)

        # We need to keep a reference to the photo image alive to 
        # prevent it being garbage collected
        self.current_image = ImageTk.PhotoImage(pil_image)
        if self.canvas_image == None:
            self.canvas_image = self.image_widget.create_image(0, 0, anchor='nw', image=self.current_image)
        else:
            self.canvas_image = self.image_widget.itemconfig(self.canvas_image, image=self.current_image)
        debug(f'loaded {self.image_index}={self.images[self.image_index]}')

        if self.show_histogram:
            self.draw_histogram(pil_image)


    def updater(self):
        '''Called regularly to see if new images have appeared on disk'''

        if self.rescan:
            debug('rescan')
            # We've been asked to rescan the directory - perhaps a file disappeared
            self.images = []
            self.image_index = None
            self.rescan = False

        # All of the files in the hot directory that end in .jpg 
        paths = [os.path.join(sys.argv[1], file) for file in os.listdir(sys.argv[1]) if file.lower().endswith('.jpg')]

        # Images that have appeared since we last looked
        new_images = [path for path in paths if path not in self.images and os.path.isfile(path)]

        if new_images != []:

            # There are new images so whereever we were, move
            # to the first new image and display it
            debug(f'saw {new_images}')
            self.image_index = len(self.images)
            self.images.extend(new_images)
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

import sys

if __name__ == '__main__':    

    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, help='Width of app window')
    parser.add_argument('--height', type=int, help='Height of app window')
    parser.add_argument('--bare', action='store_true', help='Disable window manager decoration')
    parser.add_argument('--bell', action='store_true', help='Ring the bell when new images appear')
    parser.add_argument('--debug', action='store_true', help='Print debug info to standard output')
    parser.add_argument('directory', help='Path to hot folder')
    args = parser.parse_args()

    debugging = args.debug
    tk = tkinter.Tk()
    app = Viewer(master=tk, width=args.width, height=args.height, bare=args.bare, bell=args.bell)
    tk.after(10, app.updater)
    tk.mainloop()


