import os
import sys
import time
import wx

class ImagePanel(wx.Panel):

    def __init__(self, parent, root):
        super().__init__(parent)
        self.file_path = None
        self.root = root
        self.images = []
        self.image_index = None
        screen_width, screen_height = wx.DisplaySize()
        self.max_width = screen_width - 10
        self.max_height = screen_height - 10

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_image, self.timer)

        img = wx.Image((10,10))
        self.image_ctrl = wx.StaticBitmap(self, bitmap=wx.Bitmap(img))
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddStretchSpacer()
        main_sizer.Add(self.image_ctrl, 0, wx.ALIGN_CENTRE|wx.Centre)
        main_sizer.AddStretchSpacer()

        self.SetSizer(main_sizer)
        self.SetBackgroundColour(wx.Colour(80, 80, 80))
        main_sizer.Fit(parent)
        self.Layout()
        self.SetFocus()

        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.update_image(event=None)
        self.timer.Start(250)

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        print(key_code)
        if key_code in (wx.WXK_ESCAPE, ord('Q')):
            self.Parent.Close()
        elif key_code in (ord('P'), wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT):
            self.back()
        elif key_code in (ord('N'), wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT):
            self.next()
        elif key_code in (ord('F'), wx.WXK_HOME):
            self.first()
        elif key_code in (ord('L'), wx.WXK_END):
            self.last()
        else:
            event.Skip()

    def first(self):
        self.image_index = 0
        self.load_image()

    def last(self):
        self.image_index = len(self.images) - 1
        self.load_image()

    def next(self):
        self.image_index = (self.image_index + 1) % len(self.images)
        self.load_image()

    def back(self):
        self.image_index = (self.image_index - 1) % len(self.images)
        self.load_image()

    def read_image(self, path):
        while True:
            try:
                img = wx.Image(path, wx.BITMAP_TYPE_ANY)
                return img, img.GetWidth(), img.GetHeight()
            except:
                print('retry', path)
                time.sleep(0.25)

    def load_image(self):

        if self.image_index != None:
            path = self.images[self.image_index]

            img, w, h = self.read_image(path)

            # Scale factors to apply to image to make each dimension fit
            w_scale = w / self.max_width
            h_scale = h / self.max_height

            scale = max(w_scale, h_scale)
            img = img.Scale(int(w / scale), int(h / scale))
            self.image_ctrl.SetBitmap(wx.Bitmap(img))
            self.Layout()
            self.Refresh()


    def update_image(self, event):

        paths = [os.path.join(self.root, file) for file in os.listdir(self.root) if file.lower().endswith('.jpg')]
        new_images = [path for path in paths if path not in self.images and os.path.isfile(path)]

        if new_images != []:
            print('saw', new_images)
            self.image_index = len(self.images)
            self.images.extend(new_images)
            self.load_image()



class MainFrame(wx.Frame):

    def __init__(self, root):
        super().__init__(None, title="Window Title")
        panel = ImagePanel(self, root=root)
        self.ShowFullScreen(True)



if __name__ == '__main__':
    app = wx.App(redirect=False)
    frame = MainFrame(sys.argv[1])
    app.MainLoop()
