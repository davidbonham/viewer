import os
import sys
import tkinter
from PIL import Image, ImageTk


class Viewer():

    def __init__(self, master):

        self.image_index = None      # Index of the current image
        self.images = []             # The paths of images we know about
        self.master = master

        # Set ourselves up as a full screen window
        self.screen_w = master.winfo_screenwidth()
        self.screen_h = master.winfo_screenheight()

        #Remove window manager decoration and processing of 'X' button
        #closing processing &c
        #root.overrideredirect(1)

        master.geometry("%dx%d+0+0" % (self.screen_w, self.screen_h))
        master.title('Image Viewer')
        master.configure(bg='#202020')
        master.focus_set()
        self.multibind(master, ["<Escape>", 'q', 'Q'], self.on_escape)
        self.multibind(master, ["<Left>", 'p', 'P'], self.on_left)
        self.multibind(master, ['<Right>', 'n', 'N'], self.on_right)
        self.multibind(master, ['<Home>', 'h', 'H'], self.on_home)
        self.multibind(master, ['<End>', 'e', 'E'], self.on_end)

        # We'll display our image in a label widget with no border
        self.image_widget = tkinter.Label(master)
        self.image_widget.pack()
        self.image_widget.configure(bd=0, background='#808080')

    def goto_image(self, index):
        self.image_index = index % len(self.images)
        self.load_image()

    def on_escape(self, event):
        '''Quit the application'''
        print('Quit')
        event.widget.withdraw()
        event.widget.quit()

    def on_home(self, _):
        '''Go to the first image in the list'''
        self.goto_image(0)

    def on_end(self, _):
        '''Go to the final image in the list'''
        self.goto_image(len(self.images) - 1)


    def on_left(self, _):
        '''Go to the previous image, wrapping at the start'''
        self.goto_image(self.image_index - 1)

    def on_right(self, _):
        '''Go to the next image, wrapping at the end'''
        self.goto_image(self.image_index + 1)


    def multibind(self, widget, events, handler):
        '''Bind the handler to each event in the list'''
        for item in events:
            widget.bind(item, handler)

    def load_image(self):
        '''Load the image with the current image index'''
        if self.image_index == None: return

        # Get PIL to load the image
        path = self.images[self.image_index]
        pil_image = Image.open(path, 'r')
        imgWidth, imgHeight = pil_image.size
        self.master.title(f'Image Viewer - {imgWidth}x{imgHeight} - {path}')

        # Scale the image to fit the screen - the dimension that
        # needs scaling most gives us the scale factor to use.
        w_scale = imgWidth / self.screen_w
        h_scale = imgHeight / self.screen_h
        scale = max(w_scale, h_scale)
        new_size = (int(imgWidth/scale), int(imgHeight/scale))

        pil_image = pil_image.resize(new_size) #, Image.ANTIALIAS)

        # We need to keep a reference to the photo image alive to
        # prevent it being garbage collected
        self.current_image = ImageTk.PhotoImage(pil_image)
        self.image_widget.configure(image=self.current_image)
        print('loaded', self.image_index, self.images[self.image_index])


    def updater(self):
        '''Called regularly to see if new images have appeared on disk'''

        # All of the files in the hot directory that end in .jpg
        paths = [os.path.join(sys.argv[1], file) for file in os.listdir(sys.argv[1]) if file.lower().endswith('.jpg')]

        # Images that have appeared since we last looked
        new_images = [path for path in paths if path not in self.images and os.path.isfile(path)]

        if new_images != []:

            # There are new images so whereever we were, move
            # to the first new image and display it
            print('saw', new_images)
            self.image_index = len(self.images)
            self.images.extend(new_images)
            self.load_image()

        '''We want to be called again'''
        self.master.after(250, self.updater)

import sys

if __name__ == '__main__':

    tk = tkinter.Tk()
    app = Viewer(master=tk)
    tk.after(10, app.updater)
    tk.mainloop()


